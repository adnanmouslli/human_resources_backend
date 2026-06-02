# app/routes/backup.py
# Endpoint لإنشاء وتنزيل نسخة احتياطية كاملة (.bak) من قاعدة بيانات SQL Server.
# مقتصر على super_admin فقط لحساسية البيانات.
#
# الفكرة الموحَّدة:
#   1) Flask يطلب من SQL Server BACKUP TO DISK = <مسار_يكتب_فيه_SQL_Server>
#   2) Flask يقرأ نفس الملف بنفسه ويرسله للفرونت
#   3) Flask يحذف الملف بعد الإرسال
#
# لكي تعمل هذه الفكرة، يجب أن يكون المسار مرئياً للطرفين:
#  - direct (لوكال Windows): SQL Server و Flask على نفس الـ host → نفس المسار
#  - shared (VPS مع Docker): نفس المسار mounted كـ volume في الحاويتين معاً.
#    اسم المسار قد يختلف بين host و containers، لذا نستخدم مفتاحَين:
#       BACKUP_DIR              → المسار الذي يراه Flask (داخل container أو host)
#       SQL_CONTAINER_BACKUP_DIR → المسار نفسه كما يراه SQL Server container
#    إذا كان كلا الـ Flask و SQL Server يستخدمان نفس نقطة mount، فالمسارين متطابقين.
#
# الإعدادات تُقرأ من app/config.py، ويمكن تجاوزها بمتغيرات بيئة بنفس الأسماء.

import os
import re
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
    """قراءة إعدادات الـ backup من app.config أولاً، ثم من متغيرات البيئة."""
    def _read(key, default):
        env_val = os.environ.get(key)
        if env_val is not None and env_val != '':
            return env_val
        return current_app.config.get(key, default)

    mode = (_read('BACKUP_MODE', 'direct') or 'direct').strip().lower()
    if mode not in ('direct', 'shared'):
        # توافق مع التسمية القديمة 'docker' → نحوّلها لـ shared
        mode = 'shared' if mode == 'docker' else 'direct'

    default_dir = '/var/opt/mssql/backups' if mode == 'shared' else r'C:\SQLBackups'

    cfg = {
        'mode': mode,
        # المسار كما يراه Flask
        'flask_dir': _read('BACKUP_DIR', default_dir),
    }
    # المسار كما يراه SQL Server (داخل container). إن لم يُحدَّد، نفترض نفس المسار.
    cfg['sql_dir'] = _read('SQL_CONTAINER_BACKUP_DIR', cfg['flask_dir'])
    return cfg


# ─────────────────────────────────────────────────────────────────────
# دوال مساعدة
# ─────────────────────────────────────────────────────────────────────

def _extract_db_name():
    return db.engine.url.database


def _safe_filename_component(value: str) -> str:
    return re.sub(r'[^A-Za-z0-9_\-]', '_', value or 'database')


def _delete_file_silent(path: str):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception as exc:
        current_app.logger.warning(f"[BACKUP] failed to remove temp file {path}: {exc}")


# ─────────────────────────────────────────────────────────────────────
# تنفيذ BACKUP
# ─────────────────────────────────────────────────────────────────────

def _run_backup(db_name_raw, safe_db_name, timestamp, cfg):
    """
    ينفّذ BACKUP DATABASE. SQL Server يكتب في cfg['sql_dir'] (المسار من منظوره)،
    و Flask يقرأ من cfg['flask_dir'] (المسار من منظوره). في direct mode هما نفس
    المسار؛ في shared mode هما mounted على نفس volume.
    """
    flask_dir = cfg['flask_dir']
    sql_dir = cfg['sql_dir'].rstrip('/').rstrip('\\')

    # تأكد أن Flask يستطيع رؤية المجلد
    try:
        os.makedirs(flask_dir, exist_ok=True)
    except Exception as exc:
        return None, f"تعذّر إنشاء/الوصول لمجلد النسخ الاحتياطي: {flask_dir} ({exc})"

    file_name = f"{safe_db_name}_{timestamp}.bak"
    flask_path = os.path.join(flask_dir, file_name)

    # المسار الذي نمرّره لـ SQL Server: نستخدم separator مناسب للـ container
    # (في الغالب linux container → forward slash)
    if '/' in sql_dir or cfg['mode'] == 'shared':
        sql_path = f"{sql_dir}/{file_name}"
    else:
        sql_path = os.path.join(sql_dir, file_name)

    # ملاحظة: COMPRESSION غير مدعوم على SQL Server Express Edition
    sql_cmd = (
        f"BACKUP DATABASE [{db_name_raw}] "
        f"TO DISK = :disk_path "
        f"WITH FORMAT, INIT, "
        f"NAME = :backup_name, SKIP, NOREWIND, NOUNLOAD, STATS = 10"
    )

    try:
        with db.engine.connect().execution_options(isolation_level='AUTOCOMMIT') as conn:
            conn.execute(
                text(sql_cmd),
                {
                    'disk_path': sql_path,
                    'backup_name': f"{safe_db_name}-Full Backup {timestamp}",
                },
            )
    except Exception as exc:
        _delete_file_silent(flask_path)
        return None, f"فشل تنفيذ BACKUP DATABASE: {exc}"

    if not os.path.exists(flask_path):
        return None, (
            f"تم تنفيذ BACKUP لكن Flask لا يرى الملف على المسار {flask_path}. "
            f"تأكد أن BACKUP_DIR و SQL_CONTAINER_BACKUP_DIR يشيران لنفس volume."
        )

    return flask_path, None


# ─────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────

@backup_bp.route('/database', methods=['GET'])
@token_required
def download_database_backup(user):
    """إنشاء نسخة احتياطية كاملة (.bak) للقاعدة الحالية وتنزيلها مباشرة."""
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
        f"[BACKUP] mode={cfg['mode']} user={user.id} db={db_name_raw} "
        f"flask_dir={cfg['flask_dir']} sql_dir={cfg['sql_dir']}"
    )

    flask_path, error = _run_backup(db_name_raw, safe_db_name, timestamp, cfg)

    if error:
        current_app.logger.error(f"[BACKUP] {error}")
        return jsonify({
            'message': 'فشل إنشاء النسخة الاحتياطية',
            'error': error,
            'mode': cfg['mode'],
            'hint': (
                'في shared mode تأكد أن نفس volume mounted في كلٍ من SQL Server '
                'و Flask containers، وأن المستخدم mssql داخل الـ container يستطيع '
                'الكتابة على المسار، وأن Flask يستطيع القراءة منه.'
            ),
        }), 500

    file_name = os.path.basename(flask_path)
    file_size = os.path.getsize(flask_path)
    current_app.logger.info(
        f"[BACKUP] success file={file_name} size={file_size} bytes"
    )

    @after_this_request
    def cleanup(response):
        threading.Thread(target=_delete_file_silent, args=(flask_path,), daemon=True).start()
        return response

    return send_file(
        flask_path,
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
