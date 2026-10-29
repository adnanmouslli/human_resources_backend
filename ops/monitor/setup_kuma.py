"""
تهيئة Uptime Kuma: حساب الأدمن + المراقبات + (اختياري) إشعار الإيميل.
آمن للتكرار: يضيف الناقص فقط، فيُعاد تشغيله بعد إضافة زبون جديد.
يطبع tokens مراقبات الـ push (يستخدمها ops/hr-health) بصيغة KEY=VALUE.

يُشغَّل من السيرفر داخل حاوية python مؤقتة على شبكة hr_main_network — انظر OPERATIONS.md (المراقبة).
المتغيرات: KUMA_USER, KUMA_PASSWORD, HR_CLIENTS (JSON: [{"slug","domain"}]), SERVER_IP
          SMTP_PASSWORD (اختياري: App Password لـ Gmail) + ALERT_EMAIL
"""
import json
import os
import secrets
import string

from uptime_kuma_api import MonitorType, NotificationType, UptimeKumaApi

KUMA_URL = os.environ.get("KUMA_URL", "http://uptime-kuma:3001")
USER = os.environ["KUMA_USER"]
PASSWORD = os.environ["KUMA_PASSWORD"]
CLIENTS = json.loads(os.environ["HR_CLIENTS"])
SERVER_IP = os.environ["SERVER_IP"]
ALERT_EMAIL = os.environ.get("ALERT_EMAIL", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")

# مراقبات push يغذيها ops/hr-health كل 5 دقائق؛ إن لم يصل شيء خلال 15 دقيقة تُعتبر معطلة
PUSH_CHECKS = {
    "SERVER": "health: server resources & services",
    "CONTAINERS": "health: containers",
    "DATABASE": "health: databases",
    "SYNC": "health: fingerprint sync",
    "SSH": "health: SSH logins",
}

api = UptimeKumaApi(KUMA_URL, timeout=60)
if api.need_setup():
    api.setup(USER, PASSWORD)
api.login(USER, PASSWORD)

existing = {m["name"]: m for m in api.get_monitors()}


def ensure(name, **kwargs):
    if name in existing:
        return existing[name]["id"]
    return api.add_monitor(name=name, **kwargs)["monitorID"]


http = dict(type=MonitorType.HTTP, interval=60, retryInterval=60, maxretries=2)
for client in CLIENTS:
    slug, domain = client["slug"], client["domain"]
    ensure(f"{slug}: site", url=f"https://{domain}/", expiryNotification=True, **http)
    ensure(f"{slug}: api", url=f"https://{domain}/api/health", **http)

ensure("almohtaseb-hr.com", url="https://almohtaseb-hr.com/", expiryNotification=True, **http)
ensure("jana: legacy IP:3000", url=f"http://{SERVER_IP}:3000/api/health", **http)
ensure("jana: legacy IP:4000", url=f"http://{SERVER_IP}:4000/", **http)
ensure("monitor dashboard", url="https://monitor.almohtaseb-hr.com/", expiryNotification=True, **http)
ensure("SQL Server", type=MonitorType.PORT, hostname="hr_sqlserver_temp", port=1433,
       interval=60, retryInterval=60, maxretries=2)

tokens = {}
alphabet = string.ascii_letters + string.digits
for key, name in PUSH_CHECKS.items():
    if name in existing:
        tokens[key] = api.get_monitor(existing[name]["id"])["pushToken"]
    else:
        token = "".join(secrets.choice(alphabet) for _ in range(32))
        api.add_monitor(type=MonitorType.PUSH, name=name, pushToken=token, interval=900, maxretries=0)
        tokens[key] = token

if SMTP_PASSWORD and ALERT_EMAIL:
    names = {n["name"] for n in api.get_notifications()}
    if "Email (Gmail)" not in names:
        api.add_notification(
            name="Email (Gmail)", type=NotificationType.SMTP, isDefault=True, applyExisting=True,
            smtpHost="smtp.gmail.com", smtpPort=465, smtpSecure=True,
            smtpUsername=ALERT_EMAIL, smtpPassword=SMTP_PASSWORD,
            smtpFrom=f"HR Monitor <{ALERT_EMAIL}>", smtpTo=ALERT_EMAIL,
        )

api.disconnect()
for key, token in tokens.items():
    print(f"PUSH_{key}={token}")
