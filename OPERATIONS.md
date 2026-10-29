# دليل التشغيل — نظام الموارد البشرية (المحتسب HR)

هذا الملف هو المرجع لكل ما يخص السيرفر، النشر (deploy)، إدارة الزبائن، والأمان.
اقرأه قبل أي تعديل على السيرفر أو طريقة النشر. عند إنجاز أي مهمة من [قائمة المهام](#10-قائمة-المهام)
غيّر `[ ]` إلى `[x]` وأضف التاريخ، وسجّل التغييرات المهمة في [سجل التغييرات](#9-سجل-التغييرات).

> آخر تحديث: 2026-10-29

---

## 1. البنية باختصار

صورة باك إند **واحدة** لكل الزبائن، وواجهة **واحدة** لكل الزبائن. الذي يختلف لكل زبون: إعداداته وقاعدته وملفاته.

```
المتصفح / تطبيق الموبايل / برنامج البصمة
        │ https://<client>.almohtaseb-hr.com
        ▼
nginx (على السيرفر نفسه)
 ├── /       → ملفات الواجهة المشتركة مباشرة   /srv/hr/frontend/current/browser
 └── /api/   → 127.0.0.1:<port>  → حاوية الزبون hr-<slug>  (gunicorn)
                                        │
                                        ▼
                         SQL Server (حاوية hr_sqlserver_temp)
                         قاعدة لكل زبون + مستخدم SQL خاص به
```

- **الباك إند:** صورة `hr-backend:<commit>` تُبنى من `Dockerfile.prod`، تعمل بـ gunicorn، والكود داخل الصورة.
  لكل زبون يُركَّب عند التشغيل: `app/config.py` (إعداداته وأسراره) و `uploads/` ومجلد نسخه الاحتياطية.
- **الواجهة:** بناء واحد `ng build --configuration production,saas` عنوان الـ API فيه نسبي (`/api`)،
  فيعمل البناء نفسه على دومين أي زبون.
- **العزل:** لكل زبون حاوية مستقلة، قاعدة مستقلة، مستخدم SQL يملك قاعدته فقط، `SECRET_KEY` مستقل
  (توكن زبون لا يعمل عند غيره)، ومجلد نسخ احتياطية مستقل. الحاويات تستمع على `127.0.0.1` فقط.

## 2. السيرفر

| البند | القيمة |
|---|---|
| السيرفر | Contabo VPS `38.242.132.87` — Ubuntu 24.04، 4 أنوية، 3.8GB RAM |
| الدخول | `ssh root@38.242.132.87` **بالمفتاح فقط** (كلمة السر معطّلة) + fail2ban |
| DNS | wildcard: أي `*.almohtaseb-hr.com` يشير للسيرفر تلقائياً (Contabo DNS) |
| الجدار الناري | ufw: يسمح فقط 22، 80، 443 (+ 3000، 4000 مؤقتاً لـ jana — انظر المهام) |
| منافذ Docker | Docker **يتجاوز ufw**؛ أي منفذ منشور يجب أن يكون على `127.0.0.1` أو يُضاف إلى `BLOCKED_PORTS` في `/usr/local/sbin/docker-port-guard.sh` (خدمة `docker-port-guard`، حالياً `1434 5000`) |
| SQL Server | حاوية `hr_sqlserver_temp` (2019 Express) على شبكة `hr_main_network`، ملف compose: `/root/sqlserver-new/` — رغم الاسم هي الإنتاج |
| الأسرار | `/root/.secrets/` (root فقط): `sql_sa`، `sql_hr_<client>`، `<client>_secret_key`. كل `config.py` لزبون يحوي أسراره أيضاً |
| أرشيف | `/root/archive/<name>-<date>/` — نسخ قواعد مُتحقَّق منها + ملفات قبل كل حذف أو نقل |
| نسخ احتياطي يدوي | `bash /root/backup_all_dbs.sh` ← كل القواعد إلى `/root/backups/<db>/` (لا يوجد جدولة بعد) |
| موقع الشركة | حاوية `almohtaseb-hr-portfolio` (`almohtaseb-hr.com` → 127.0.0.1:5000) |

### البنية الجديدة على السيرفر
```
/srv/hr/
├── src/backend/              نسخة git من الباك إند (production) — منها تُبنى الصور، وفيها ops/hr
├── default-image             الـ commit المستخدم افتراضياً للزبائن الجدد و hr deploy
├── frontend/releases/<id>/   كل نسخة واجهة في مجلد
├── frontend/current          رابط للنسخة الفعّالة (التبديل = نشر/رجوع فوري)
├── shared/                   ملفات مشتركة (firebase-service-account.json)
├── logs/                     سجلات البناء والإنشاء
└── clients/<slug>/
    ├── client.env            DOMAIN, PORT, DB, IMAGE_TAG …  (يغيّره hr deploy)
    ├── compose.yml           مولَّد — لا تعدّله يدوياً
    ├── config.py             إعدادات وأسرار الزبون (600/640)
    └── uploads/              ملفات الزبون
```
- الأمر `hr` = `/usr/local/bin/hr` → `/srv/hr/src/backend/ops/hr` (مصدره هذا الريبو).
- النسخ الاحتياطية من داخل النظام لكل زبون: `/var/lib/docker/volumes/hr_backups/_data/<slug>/`.
- مواقع nginx: `/etc/nginx/sites-available/<domain>` (يولّدها hr). الشهادات Let's Encrypt تتجدد تلقائياً (`certbot.timer`).

### الزبائن الحاليون
`hr status` هو المرجع الدائم؛ هذا الجدول للتوثيق فقط.

| الزبون | الدومين | المنفذ الداخلي | القاعدة / مستخدمها | ملاحظات |
|---|---|---|---|---|
| jana | jana.almohtaseb-hr.com | 31003 | hr_1 / hr_jana | **إنتاج**. منافذ مباشرة مؤقتة IP:3000 و IP:4000 (انظر أدناه) |
| askf | askf.almohtaseb-hr.com | 31002 | hr_2 / hr_askf | زبون حقيقي لم يبدأ بعد — يصلح للتجارب |
| sdi | sdi.almohtaseb-hr.com | 31001 | hr_sdi / hr_sdi | أُنشئ بـ `hr new` (أول زبون في البنية الجديدة) |

**منافذ jana المباشرة (انتقالي):** برنامج مزامنة البصمة ونسخ تطبيق الموبايل القديمة يتصلون بـ `http://IP:3000/api`،
وبعض الموظفين يفتحون `http://IP:4000`. يخدمهما nginx ويوجّههما لحاوية jana:
`/srv/hr/clients/jana/nginx-legacy-ports.conf` (مفعّل كـ `sites-enabled/jana-legacy-ports`).
من ما زال يستخدمهما: `/var/log/nginx/jana-legacy.access.log`.

## 3. الكود والإعدادات (قواعد)

- **`run.py`** في git ويقرأ `HOST/PORT/DEBUG/CREATE_SUPER_ADMIN` من متغيرات البيئة ثم `app/config.py` ثم قيم آمنة (debug مطفأ).
- **`app/config.py`** خاص بكل بيئة وفي `.gitignore`. القالب **`app/config.example.py`** في git:
  أي إعداد جديد يُضاف للقالب (hr يولّد config.py لكل زبون منه، ويضيف إعدادات `BACKUP_*`).
- **`entrypoint.sh`** في git، ينتظر القاعدة باستخدام `config.py` (بلا كلمات سر).
- **`Dockerfile.prod` + `gunicorn.conf.py`**: عملية gunicorn **واحدة** × 8 threads، timeout 600s —
  لأن `create_app()` يعدّل بنية القاعدة عند الإقلاع وتعدد العمليات يكرر ذلك بالتوازي.
  `Dockerfile.prod.dockerignore` يمنع دخول الأسرار للصورة. `Dockerfile` المحلي للتطوير فقط.
- **تعديلات بنية القاعدة:** لا يوجد Alembic في الإنتاج، و `db.create_all()` لا يضيف أعمدة لجداول موجودة.
  العمود الجديد يُضاف في `create_app()` (`app/__init__.py`) بنمط "إن لم يوجد أضفه" الآمن للتكرار —
  هكذا تحصل كل قواعد الزبائن عليه تلقائياً عند أول تشغيل للصورة الجديدة.
- **الواجهة:** `environment.ts` كما هو للتطوير (⚠️ يشير حالياً إلى jana الإنتاج). بناء الزبائن يستخدم
  `--configuration production,saas` الذي يستبدل `api-target.ts` بـ `api-target.saas.ts` (`/api`).
- **لا تعدّل أي ملف متتبَّع في git على السيرفر يدوياً**: التعديل في git ثم نشر.

## 4. النشر (Deploy)

المستودعات: الباك إند `adnanmouslli/human_resources_backend` والواجهة `adnanmouslli/human_resources` (فرع `production`).
السكربتات في `hr-dev/deploy/` على جهاز التطوير (Git Bash).

### الباك إند
```bash
git push origin production                     # أولاً
./deploy/deploy-backend-saas.sh                # كل الزبائن، واحد تلو الآخر
./deploy/deploy-backend-saas.sh jana           # زبون واحد
```
يكافئ يدوياً على السيرفر: `cd /srv/hr/src/backend && git pull && hr build && hr deploy --all`.
- `hr build` يبني `hr-backend:<commit>` (دقيقة تقريباً، ثوانٍ إن لم تتغير المكتبات) ويجعلها الافتراضية.
- `hr deploy` ينقل كل زبون للصورة ويتحقق من `/api/health`؛ إن فشل زبون **يرجع تلقائياً** للصورة السابقة ويتوقف قبل الباقين.
- التوقف لكل زبون ~5 ثوانٍ أثناء إعادة إنشاء الحاوية.
- **الرجوع:** `hr deploy <client> <tag-سابق>` (الصور المتاحة: `docker image ls hr-backend`).

### الواجهة
```bash
git push origin production                     # يُنصح (السكربت يحذّر إن وُجدت تعديلات غير مرفوعة)
./deploy/release-frontend-saas.sh              # بناء + رفع + تفعيل — لكل الزبائن معاً
```
- يرفع إلى `/srv/hr/frontend/releases/<commit>-<time>` ثم يبدّل `current` — بلا توقف، ويحتفظ بآخر 5 نسخ.
- **الرجوع:** `ssh root@38.242.132.87 'cd /srv/hr/frontend && ln -sfn releases/<old> current.tmp && mv -T current.tmp current'`.

### إن تغيّر الاثنان
انشر الباك إند أولاً (يجب أن يبقى متوافقاً مع الواجهة القديمة)، ثم الواجهة.

## 5. أوامر `hr` (على السيرفر كـ root)

| الأمر | الوظيفة |
|---|---|
| `hr status` | جدول الزبائن: الحالة، الصحة، الصورة، انتهاء الشهادة |
| `hr logs <client> [--since 10m] [--tail 100]` | سجلات حاوية الزبون |
| `hr build [ref]` | بناء صورة من git (افتراضياً `origin/production`) |
| `hr deploy <client\|--all> [tag]` | نقل زبون/الكل لصورة، مع رجوع تلقائي |
| `hr new <client> <domain>` | زبون جديد كامل (انظر 6) |
| `hr adopt <client> <domain>` | نقل زبون موجود من خارج البنية (استُخدم لـ askf و jana) |

## 6. إضافة زبون جديد

1. **الدومين:** نطاق فرعي `<name>.almohtaseb-hr.com` جاهز فوراً (wildcard). دومين خاص بالزبون: يضيف هو سجل
   `A` إلى `38.242.132.87` أولاً (`hr new` يتحقق ويرفض إن لم يكن يشير للسيرفر).
2. على السيرفر:
   ```bash
   HR_ADMIN_USER=<username> HR_ADMIN_PASSWORD='<password>' hr new <client> <domain>
   ```
   بدون `HR_ADMIN_PASSWORD` تُولَّد كلمة سر عشوائية وتُحفظ في `/srv/hr/clients/<client>/admin-initial-password`.
3. ينشئ: قاعدة `hr_<client>` + مستخدم SQL يملكها فقط، `config.py` بأسرار عشوائية، الحاوية، nginx، شهادة SSL،
   ويتحقق من https. إن فشلت خطوة يطبع ما أُنشئ ليُنظَّف.
4. القاعدة فارغة + حساب `super_admin` واحد (لا يُستخدم `create_super_admin()` الذي ينشئ admin/admin).

## 7. قواعد للعمل على هذا النظام (للمطوّر وللـ AI agent)

- **jana إنتاج:** أي تغيير على السيرفر يُعرض أولاً مع أثره ومدة التوقف، ولا يُنفَّذ إلا بموافقة صاحب المشروع. خطوة بخطوة.
- قبل أي حذف أو استبدال: نسخة احتياطية **مُتحقَّق منها** (`BACKUP … WITH CHECKSUM` + `RESTORE VERIFYONLY`) وأرشفة في `/root/archive/`.
- لا تطبع الأسرار أبداً. لتمرير كلمة سر لـ SQL: ملف `.sql` يحوي `$(VAR)` + `sqlcmd -v VAR="$VAR"` من البيئة
  (نمط `sql_run` في `ops/hr`). ملفات `.sql` المنسوخة للحاوية تحتاج `chmod 644` (sqlcmd يعمل كمستخدم mssql).
- عند تعديل ufw: فعّل أولاً `systemd-run --on-active=3m ufw --force disable` كصمام أمان، ثم اختبر اتصال SSH جديداً وألغه في نفس الأمر.
- الإنترنت على جهاز التطوير بطيء جداً (~30KB/s): البناء والتنزيلات واختبارات النقل تُجرى على السيرفر.
- قبل `git push`: `git fetch` وتأكد أن لا commits جديدة من غيرك. لا `--force` أبداً.
- لا تستخدم `docker compose down` في مجلدات البنية القديمة (أسماء مشاريع مشتركة)؛ احذف الحاويات بالاسم.
- بعد إنجاز أي بند من المهام: حدّثه هنا إلى `[x]` مع التاريخ.

## 8. الأمان — الوضع الحالي

| البند | الحالة |
|---|---|
| SSH | مفاتيح فقط (`/etc/ssh/sshd_config.d/00-hardening.conf`)، `PermitRootLogin prohibit-password`، fail2ban |
| ufw | مفعّل: 22/80/443 (+3000/4000 مؤقتاً) |
| SQL Server | المنفذ 1434 مغلق من الإنترنت؛ كلمة سر `sa` قوية؛ كل زبون بمستخدم يملك قاعدته فقط |
| التطبيق | gunicorn بلا debugger؛ `SECRET_KEY` عشوائي لكل زبون؛ الحاويات على 127.0.0.1 |
| Webmin | أُزيل |
| مفتوح بعد | endpoints البصمة بلا مصادقة، منافذ jana المباشرة، GitHub token على السيرفر — انظر المهام |

## 9. سجل التغييرات

### 2026-10-28
- فحص شامل للسيرفر. نسخ احتياطي لكل القواعد.
- SSH بالمفاتيح فقط + fail2ban. حذف Webmin. jana nginx → `127.0.0.1:3000`.
- إيقاف debugger في jana. `run.py` أصبح في git ويقرأ الإعدادات من `config.py` (commit `c62b794`).
- إغلاق المنفذ 1434 (كان يتعرض لهجوم تخمين: 34,584 محاولة على `sa` بلا نجاح) وخدمة `docker-port-guard`.
- حذف الزبائن المنتهين: saleh, al-azhar (hr_3), alwahed (hr_4), abozafer (hr_5) — مؤرشفين.
- ufw مفعّل (22/80/443)، إغلاق المنفذ 5000.

### 2026-10-29
- `SECRET_KEY` عشوائي لـ jana و askf (كان `"test"` = إمكانية تزوير توكن أدمن). سجّل كل المستخدمين خروجاً.
- مستخدمو SQL مستقلون `hr_jana` و `hr_askf`، تغيير كلمة سر `sa`. `entrypoint.sh` في git بلا كلمات سر (`982cb50`).
- تنظيف: حذف قواعد hr_riyad و hr-test و test، مجلد clients/test، شهادة afnantex، 12 حاوية ميتة وصور (تحرير 57GB).
- إغلاق المنفذ 3001 (debugger askf القديم).
- تعديل برنامج مزامنة البصمة محلياً (الدومين + `X-Sync-Key`) — بانتظار تطبيقه عند jana.
- **البنية الجديدة:** `Dockerfile.prod`، `gunicorn.conf.py`، بناء الواجهة `saas`، الأمر `ops/hr`، `/srv/hr`.
- زبون جديد **sdi** بـ `hr new`. إصلاح restore الذي يرجع 500 رغم النجاح (`c9b3f30`).
- نقل **askf** ثم **jana** إلى البنية الجديدة بـ `hr adopt` (بلا تسجيل خروج، بلا توقف للدومين، ~2.6 ثانية للمنافذ المباشرة).
  حذف بنية askf القديمة. حاويات jana القديمة **موقوفة** للرجوع.
- `deploy-jana.sh` أُلغي واستُبدل بـ `deploy-backend-saas.sh` و `release-frontend-saas.sh`.

## 10. قائمة المهام

### مُنجز
- [x] SSH بالمفاتيح + fail2ban + حذف Webmin (2026-10-28)
- [x] إغلاق 1434/5000/3001 من الإنترنت + ufw (2026-10-28/29)
- [x] إيقاف debugger + `run.py` و `entrypoint.sh` في git (2026-10-28/29)
- [x] `SECRET_KEY` عشوائي + مستخدم SQL لكل زبون + كلمة سر `sa` جديدة (2026-10-29)
- [x] حذف الزبائن المنتهين والقواعد والملفات غير المستخدمة (2026-10-28/29)
- [x] البنية الجديدة + `hr` + زبون sdi + نقل askf و jana (2026-10-29)
- [x] إلغاء `deploy-jana.sh` وسكربتات النشر الجديدة (2026-10-29)

### مفتوح — أمان
- [ ] **مصادقة endpoints البصمة** `/api/fingerprint/sync|check-in|check-out|sync-excel` (حالياً مفتوحة لأي أحد).
      برنامج المزامنة جاهز محلياً (`Egypt-Project/برنامج المزامنة للسيرفر/zkteco-sync`: دومين + `X-Sync-Key` من `sync_key.txt`).
      **بانتظار أن تطبّقه jana** — لا تفعّل الفحص قبل ذلك. ثم: decorator `sync_key_required` + `SYNC_API_KEY` و `SYNC_KEY_MODE` (off|log|enforce) في config.py → log → enforce.
- [ ] **إغلاق منافذ jana المباشرة 3000/4000** بعد انتقال برنامج البصمة وتطبيق الموبايل والموظفين للدومين
      (تحقق من `/var/log/nginx/jana-legacy.access.log`)، ثم: حذف `sites-enabled/jana-legacy-ports` + `ufw delete allow 3000/tcp` و `4000/tcp`.
- [ ] استبدال GitHub token في `/root/.git-credentials` بـ deploy key للقراءة فقط.
- [ ] تحديثات النظام (~98 حزمة) + reboot — يحتاج نافذة توقف.
- [ ] (صاحب المشروع) تغيير كلمة سر root بـ `passwd` (للـ VNC console) وحذف `Egypt-Project/password_vps.txt`.
- [ ] (صاحب المشروع) تغيير كلمة سر أدمن sdi الضعيفة بعد أول دخول للزبون.

### مفتوح — تطبيقات
- [ ] **تطبيق الموبايل:** `lib/core/constant/App_link.dart` معدّل محلياً إلى `https://jana.almohtaseb-hr.com/api` (غير مرفوع ولا منشور) — إصدار نسخة جديدة.
- [ ] تطبيق الموبايل: تسجيل خروج تلقائي عند 401 (حالياً يعيد إرسال توكن منتهٍ للأبد).
- [ ] تطبيق الموبايل لعدة زبائن (كود الشركة عند الدخول → دومينها).
- [ ] خطأ قديم: `'date' is not a recognized built-in function` في فحص غياب الموظف (SQL Server لا يدعم الدالة).
- [ ] مستقبلاً: مزامنة البصمة بـ ZKTeco ADMS/Push بدل برنامج عند الزبون (يحتاج موديل أجهزة jana).

### مفتوح — البنية والتشغيل
- [ ] **نسخ احتياطي مجدول** لكل الزبائن (القواعد + uploads) + نسخة خارج السيرفر (rclone) + تنبيه عند الفشل.
- [ ] **مراقبة:** Uptime Kuma (المواقع + SSL) و Beszel (الموارد).
- [ ] أمر `hr remove <client>` (نسخة نهائية + أرشفة + حذف).
- [ ] بعد استقرار jana: حذف حاويتي `hr_flask_riyad` و `hr-frontend-riyad` وصورهما، وأرشفة `/root/hr`.
- [ ] تنظيف المجلدات القديمة: `/root/hr2`، `/root/hr_any`، `/root/hr_multi_tenant`، `/root/human_resources`، `/root/human_resources_backend`، `/root/dist`، `/root/sqlserver` + 22 volume غير مستخدم (افحص محتواها قبل الحذف).
- [ ] حاوية SQL: إعادة إنشائها لإصلاح healthcheck (مسار sqlcmd خاطئ → unhealthy دائماً) وإزالة كلمة سر `sa` القديمة من env — يحتاج توقف للقواعد.
- [ ] القواعد على `FULL recovery` بلا نسخ للـ log (ملفات log تكبر) — `SIMPLE` أو نسخ log.
- [ ] حد حجم سجلات Docker عامّاً (`/etc/docker/daemon.json`) و journald (4GB حالياً).
