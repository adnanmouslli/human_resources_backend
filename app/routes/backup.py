# app/routes/backup.py
# Endpoint لإنشاء وتنزيل نسخة احتياطية كاملة (.bak) من قاعدة بيانات SQL Server.
# مقتصر على super_admin فقط لحساسية البيانات.
#
# يدعم وضعين:
#  - direct (لوكال Windows / SQL Server محلي):
#        BACKUP TO DISK مباشرة في مجلد على نفس السيرفر
#  - docker (VPS مع SQL Server داخل container):
#        BACKUP داخل المسار /var/opt/mssql/data ثم docker cp للنقل خارج
#
# الإعدادات تُقرأ من app/config.py (المفاتيح أدناه)، ويمكن تجاوزها بمتغيرات بيئة
# بنفس الأسماء عند الحاجة:
#   BACKUP_MODE              = "direct" | "docker"
#   BACKUP_DIR               = مسار يكتب فيه الملف النهائي (host)
#   SQL_DOCKER_CONTAINER     = اسم الـ container (وضع docker)
#   SQL_CONTAINER_BACKUP_DIR = مسار داخل الـ container للكتابة المؤقتة

import os
import re
import subprocess
import threading
from datetime import datetime

from flask import Blueprint, current_app, jsonify, send_file, after_this_request
from sqlalchemy import text

from app import db
from app.utils import token_required

backup_bp = Blueprint('backup', __name__, url_prefix='/api/backup')


# ─────────────────────────────────────────────────────────────────────
# الإعدادات
# ─────────────────────────────────────────────────────────────────────

def _get_config():
    """
    قراءة إعدادات الـ backup من app.config أولاً، ثم من متغيرات البيئة كاحتياط.
    """
    def _read(key, default):
        # متغير بيئة يتجاوز config (مفيد للنشر على VPS بدون تعديل الكود)
        env_val = os.environ.get(key)
        if env_val is not None and env_val != '':
            return env_val
        return current_app.config.get(key, default)

    mode = (_read('BACKUP_MODE', 'direct') or 'direct').strip().lower()
    if mode not in ('direct', 'docker'):
        mode = 'direct'

    default_dir = '/root/backups' if mode == 'docker' else r'C:\SQLBackups'

    return {
        'mode': mode,
        'host_dir': _read('BACKUP_DIR', default_dir),
        'container': _read('SQL_DOCKER_CONTAINER', 'hr_sqlserver_temp'),
        'container_dir': _read('SQL_CONTAINER_BACKUP_DIR', '/var/opt/mssql/data'),
    }


# ─────────────────────────────────────────────────────────────────────
# دوال مساعدة
# ─────────────────────────────────────────────────────────────────────

def _extract_db_name():
    """يستخرج اسم قاعدة البيانات الحالية من الـ engine."""
    return db.engine.url.database


def _safe_filename_component(value: str) -> str:
    """تنظيف اسم القاعدة ليكون آمناً ضمن مسار ملف."""
    return re.sub(r'[^A-Za-z0-9_\-]', '_', value or 'database')


def _delete_file_silent(path: str):
    """يحذف الملف بهدوء بعد الإرسال."""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception as exc:
        current_app.logger.warning(f"[BACKUP] failed to remove temp file {path}: {exc}")


def _run_docker_cmd(args, timeout=600):
    """
    تشغيل أمر docker مع التقاط stdout/stderr.
    يعيد (returncode, stdout, stderr).
    """
    try:
        result = subprocess.run(
            ['docker', *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return 127, '', "أمر 'docker' غير موجود في PATH"
    except subprocess.TimeoutExpired:
        return 124, '', f"انتهت مهلة تنفيذ أمر docker ({timeout}s)"
    except Exception as exc:
        return 1, '', str(exc)


# ─────────────────────────────────────────────────────────────────────
# تنفيذ BACKUP — وضع direct (Windows لوكال)
# ─────────────────────────────────────────────────────────────────────

def _backup_direct(db_name_raw, safe_db_name, timestamp, host_dir):
    """
    BACKUP TO DISK مباشرة. يتوقع أن SQL Server يكتب في مسار host
    لذا host_dir يجب أن يكون قابلاً للكتابة من حساب خدمة SQL Server.
    """
    try:
        os.makedirs(host_dir, exist_ok=True)
    except Exception as exc:
        return None, f"تعذّر إنشاء مجلد النسخ الاحتياطي: {host_dir} ({exc})"

    file_name = f"{safe_db_name}_{timestamp}.bak"
    host_path = os.path.join(host_dir, file_name)

    sql_cmd = (
        f"BACKUP DATABASE [{db_name_raw}] "
        f"TO DISK = :disk_path "
        f"WITH FORMAT, INIT, COMPRESSION, "
        f"NAME = :backup_name, SKIP, NOREWIND, NOUNLOAD, STATS = 10"
    )

    try:
        with db.engine.connect().execution_options(isolation_level='AUTOCOMMIT') as conn:
            conn.execute(
                text(sql_cmd),
                {
                    'disk_path': host_path,
                    'backup_name': f"{safe_db_name}-Full Backup {timestamp}",
                },
            )
    except Exception as exc:
        _delete_file_silent(host_path)
        return None, f"فشل تنفيذ BACKUP DATABASE: {exc}"

    if not os.path.exists(host_path):
        return None, "تم تنفيذ BACKUP لكن لم يُعثر على الملف الناتج"

    return host_path, None


# ─────────────────────────────────────────────────────────────────────
# تنفيذ BACKUP — وضع docker (VPS مع container)
# ─────────────────────────────────────────────────────────────────────

def _backup_docker(db_name_raw, safe_db_name, timestamp, cfg):
    """
    BACKUP داخل container ثم docker cp للنقل خارج.
    نفس منطق السكربت اليدوي:
      1) BACKUP TO DISK = /var/opt/mssql/data/<file>.bak  (يكتب داخل container)
      2) docker cp <container>:/path  <host_dir>/<file>.bak
      3) docker exec <container> rm /path
    """
    host_dir = cfg['host_dir']
    container = cfg['container']
    container_dir = cfg['container_dir'].rstrip('/')

    try:
        os.makedirs(host_dir, exist_ok=True)
    except Exception as exc:
        return None, f"تعذّر إنشاء مجلد host: {host_dir} ({exc})"

    file_name = f"{safe_db_name}_{timestamp}.bak"
    container_path = f"{container_dir}/{file_name}"
    host_path = os.path.join(host_dir, file_name)

    # 1) BACKUP داخل الـ container (نستخدم SQLAlchemy لأن Flask متصل بنفس الـ SQL Server)
    sql_cmd = (
        f"BACKUP DATABASE [{db_name_raw}] "
        f"TO DISK = :disk_path "
        f"WITH FORMAT, INIT, COMPRESSION, "
        f"NAME = :backup_name, SKIP, NOREWIND, NOUNLOAD, STATS = 10"
    )

    try:
        with db.engine.connect().execution_options(isolation_level='AUTOCOMMIT') as conn:
            conn.execute(
                text(sql_cmd),
                {
                    'disk_path': container_path,
                    'backup_name': f"{safe_db_name}-Full Backup {timestamp}",
                },
            )
    except Exception as exc:
        # نظّف داخل الـ container إن كان قد كتب جزئياً
        _run_docker_cmd(['exec', container, 'rm', '-f', container_path])
        return None, f"فشل تنفيذ BACKUP DATABASE داخل container: {exc}"

    # 2) نسخ الملف خارج الـ container إلى host
    rc, out, err = _run_docker_cmd(
        ['cp', f'{container}:{container_path}', host_path],
        timeout=900,  # 15 دقيقة للملفات الكبيرة
    )
    if rc != 0:
        _run_docker_cmd(['exec', container, 'rm', '-f', container_path])
        return None, f"فشل نسخ الملف من الـ container: {err.strip() or out.strip()}"

    # 3) حذف الملف من داخل الـ container
    _run_docker_cmd(['exec', container, 'rm', '-f', container_path])

    if not os.path.exists(host_path):
        return None, "لم يُعثر على الملف بعد النسخ من الـ container"

    return host_path, None


# ─────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────

@backup_bp.route('/database', methods=['GET'])
@token_required
def download_database_backup(user):
    """
    إنشاء نسخة احتياطية كاملة (.bak) للقاعدة الحالية وتنزيلها مباشرة.
    """
    if not user.is_super_admin():
        return jsonify({'message': 'غير مصرح — هذه العملية لـ super_admin فقط'}), 403

    db_name_raw = _extract_db_name()
    if not db_name_raw:
        return jsonify({'message': 'تعذّر تحديد اسم قاعدة البيانات'}), 500

    # حماية ضد SQL injection (لا يمكن parameter binding مع DDL)
    if not re.match(r'^[A-Za-z0-9_\-]+$', db_name_raw):
        return jsonify({'message': 'اسم قاعدة البيانات يحوي رموزاً غير مدعومة'}), 500

    cfg = _get_config()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_db_name = _safe_filename_component(db_name_raw)

    current_app.logger.info(
        f"[BACKUP] mode={cfg['mode']} user={user.id} db={db_name_raw}"
    )

    if cfg['mode'] == 'docker':
        host_path, error = _backup_docker(db_name_raw, safe_db_name, timestamp, cfg)
    else:
        host_path, error = _backup_direct(
            db_name_raw, safe_db_name, timestamp, cfg['host_dir']
        )

    if error:
        current_app.logger.error(f"[BACKUP] {error}")
        return jsonify({
            'message': 'فشل إنشاء النسخة الاحتياطية',
            'error': error,
            'mode': cfg['mode'],
            'hint': (
                'تأكد من صلاحيات حساب خدمة SQL Server على مجلد الكتابة، '
                'وفي وضع docker تأكد أن العملية تملك صلاحية تنفيذ docker.'
            ),
        }), 500

    file_name = os.path.basename(host_path)
    file_size = os.path.getsize(host_path)
    current_app.logger.info(
        f"[BACKUP] success file={file_name} size={file_size} bytes"
    )

    # حذف الملف من host بعد إرساله
    @after_this_request
    def cleanup(response):
        threading.Thread(target=_delete_file_silent, args=(host_path,), daemon=True).start()
        return response

    return send_file(
        host_path,
        mimetype='application/octet-stream',
        as_attachment=True,
        download_name=file_name,
    )


@backup_bp.route('/database/info', methods=['GET'])
@token_required
def get_backup_info(user):
    """معلومات سريعة قبل البدء بالنسخ الاحتياطي."""
    if not user.is_super_admin():
        return jsonify({'message': 'غير مصرح'}), 403

    db_name_raw = _extract_db_name()
    cfg = _get_config()

    info = {
        'database_name': db_name_raw,
        'last_backup_date': None,
        'database_size_mb': None,
        'mode': cfg['mode'],
    }

    try:
        with db.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT TOP 1 backup_finish_date "
                    "FROM msdb.dbo.backupset "
                    "WHERE database_name = :db AND type = 'D' "
                    "ORDER BY backup_finish_date DESC"
                ),
                {'db': db_name_raw},
            ).fetchone()
            if row and row[0]:
                info['last_backup_date'] = row[0].isoformat()

            size_row = conn.execute(
                text(
                    "SELECT SUM(CAST(size AS BIGINT)) * 8.0 / 1024 "
                    "FROM sys.master_files WHERE database_id = DB_ID(:db)"
                ),
                {'db': db_name_raw},
            ).fetchone()
            if size_row and size_row[0] is not None:
                info['database_size_mb'] = round(float(size_row[0]), 2)
    except Exception as exc:
        current_app.logger.warning(f"[BACKUP][INFO] could not read msdb/master_files: {exc}")

    return jsonify(info), 200
