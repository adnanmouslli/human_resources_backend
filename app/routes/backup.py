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

from flask import Blueprint, current_app, jsonify, request, send_file, after_this_request
from sqlalchemy import text
from werkzeug.utils import secure_filename

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


def _pyodbc_connect(database=None, autocommit=True):
    """
    يفتح pyodbc connection مستقل عن SQLAlchemy (للتحكم في autocommit).
    database=None → يستخدم نفس قاعدة البيانات في URL؛ مرّر 'master' للـ RESTORE
    حيث لا يجوز أن تكون متصلاً بالقاعدة المُراد استبدالها.
    """
    import pyodbc
    url = db.engine.url
    target_db = database if database is not None else url.database
    conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={url.host}"
        f"{',' + str(url.port) if url.port else ''};"
        f"DATABASE={target_db};"
        f"UID={url.username};"
        f"PWD={url.password};"
    )
    return pyodbc.connect(conn_str, autocommit=autocommit)


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

    # ملاحظات:
    # - COMPRESSION غير مدعوم على SQL Server Express Edition
    # - لا نضع STATS لأنه يُرسل رسائل progress عبر pyodbc تتسبب في إنهاء
    #   الـ statement مبكراً قبل اكتمال BACKUP فعلياً.
    sql_cmd = (
        f"BACKUP DATABASE [{db_name_raw}] "
        f"TO DISK = :disk_path "
        f"WITH FORMAT, INIT, "
        f"NAME = :backup_name, SKIP, NOREWIND, NOUNLOAD"
    )

    # نستخدم pyodbc connection مستقل عن SQLAlchemy حتى نتمكن من ضبط
    # autocommit قبل أي عملية. SQLAlchemy raw_connection يبدأ transaction
    # تلقائياً حتى مع isolation_level='AUTOCOMMIT'، وهذا يفشل BACKUP.
    try:
        raw_conn = _pyodbc_connect(autocommit=True)
        try:
            cursor = raw_conn.cursor()
            cursor.execute(
                sql_cmd.replace(':disk_path', '?').replace(':backup_name', '?'),
                (sql_path, f"{safe_db_name}-Full Backup {timestamp}"),
            )
            # استهلاك أي result sets إضافية حتى نتأكد أن BACKUP اكتمل
            try:
                while cursor.nextset():
                    pass
            except Exception:
                pass
            cursor.close()
        finally:
            raw_conn.close()
    except Exception as exc:
        _delete_file_silent(flask_path)
        return None, f"فشل تنفيذ BACKUP DATABASE: {exc}"

    # تشخيص: نسجّل ما يراه Flask في المجلد فور انتهاء BACKUP
    try:
        listing = sorted(os.listdir(flask_dir))
        current_app.logger.info(
            f"[BACKUP] flask sees in {flask_dir}: {listing}"
        )
    except Exception as exc:
        current_app.logger.warning(f"[BACKUP] couldn't list flask_dir: {exc}")

    if not os.path.exists(flask_path):
        # حاول مرة أخرى بعد لحظة قصيرة — في حال كان هناك تأخير في الـ filesystem sync
        import time
        time.sleep(1.0)

    if not os.path.exists(flask_path):
        try:
            listing = sorted(os.listdir(flask_dir))
        except Exception:
            listing = ['<unreadable>']
        return None, (
            f"تم تنفيذ BACKUP لكن Flask لا يرى الملف على المسار {flask_path}. "
            f"محتوى المجلد كما يراه Flask: {listing}. "
            f"تأكد أن BACKUP_DIR و SQL_CONTAINER_BACKUP_DIR يشيران لنفس volume."
        )

    return flask_path, None


# ─────────────────────────────────────────────────────────────────────
# تنفيذ RESTORE
# ─────────────────────────────────────────────────────────────────────

def _read_logical_files(sql_path):
    """
    يقرأ أسماء الملفات المنطقية (logical names) داخل ملف الـ .bak عبر
    RESTORE FILELISTONLY. نحتاجها لبناء عبارات MOVE الصحيحة عند الاستعادة.
    يُرجع (rows, error) حيث rows قائمة dicts بـ LogicalName و Type.
    """
    try:
        raw_conn = _pyodbc_connect(database='master', autocommit=True)
        try:
            cursor = raw_conn.cursor()
            cursor.execute("RESTORE FILELISTONLY FROM DISK = ?", (sql_path,))
            columns = [col[0] for col in cursor.description]
            rows = [dict(zip(columns, r)) for r in cursor.fetchall()]
            cursor.close()
            return rows, None
        finally:
            raw_conn.close()
    except Exception as exc:
        return None, f"تعذّر قراءة محتوى ملف النسخة الاحتياطية: {exc}"


def _run_restore(db_name_raw, sql_path):
    """
    يستعيد القاعدة db_name_raw من ملف .bak الموجود على sql_path (المسار من
    منظور SQL Server). الخطوات:
      1) قراءة الـ logical file names من الملف لبناء عبارات MOVE.
      2) تحديد المسار الفيزيائي الحالي لملفات القاعدة (data/log) لإعادة
         توجيه MOVE إليها — حتى لا نكتب فوق مسارات قد لا تكون موجودة.
      3) عزل القاعدة (SINGLE_USER + ROLLBACK IMMEDIATE) لطرد الاتصالات.
      4) RESTORE DATABASE ... WITH REPLACE, MOVE ...
      5) إعادة القاعدة لوضع MULTI_USER.
    كل ذلك عبر اتصال على master (لا يجوز أن نكون متصلين بالقاعدة المُستعادة).
    """
    # أولاً نقرأ الملفات المنطقية داخل الـ .bak
    filelist, error = _read_logical_files(sql_path)
    if error:
        return error
    if not filelist:
        return "ملف النسخة الاحتياطية لا يحتوي على ملفات صالحة للاستعادة."

    try:
        raw_conn = _pyodbc_connect(database='master', autocommit=True)
    except Exception as exc:
        return f"تعذّر الاتصال بـ master لتنفيذ الاستعادة: {exc}"

    try:
        cursor = raw_conn.cursor()

        # المسارات الفيزيائية الحالية لملفات القاعدة (إن كانت موجودة) لنعيد
        # استخدامها. إذا لم تكن القاعدة موجودة، نستخدم المسار الافتراضي للسيرفر.
        existing_paths = {}
        try:
            cursor.execute(
                "SELECT mf.name, mf.physical_name "
                "FROM sys.master_files mf "
                "WHERE mf.database_id = DB_ID(?)",
                (db_name_raw,),
            )
            for name, physical in cursor.fetchall():
                existing_paths[name] = physical
        except Exception:
            existing_paths = {}

        # المجلد الافتراضي لملفات البيانات (للملفات المنطقية الجديدة غير الموجودة)
        default_data_dir = None
        try:
            cursor.execute(
                "SELECT CAST(SERVERPROPERTY('InstanceDefaultDataPath') AS NVARCHAR(4000))"
            )
            row = cursor.fetchone()
            if row and row[0]:
                default_data_dir = row[0]
        except Exception:
            default_data_dir = None

        def _physical_for(logical_name, file_type):
            # 1) إن كان للقاعدة الحالية ملف بنفس الاسم المنطقي → نكتب فوقه
            if logical_name in existing_paths:
                return existing_paths[logical_name]
            # 2) وإلا نبني مساراً في المجلد الافتراضي
            ext = '.ldf' if (file_type or '').upper().startswith('L') else '.mdf'
            base = _safe_filename_component(logical_name)
            if default_data_dir:
                sep = '\\' if '\\' in default_data_dir else '/'
                return f"{default_data_dir.rstrip('/').rstrip(chr(92))}{sep}{base}{ext}"
            # 3) كملاذ أخير، بجانب ملف الـ bak
            sql_dir = os.path.dirname(sql_path)
            sep = '\\' if '\\' in sql_dir else '/'
            return f"{sql_dir}{sep}{base}{ext}"

        # بناء عبارات MOVE
        move_clauses = []
        move_params = []
        for f in filelist:
            logical = f.get('LogicalName')
            ftype = f.get('Type')
            physical = _physical_for(logical, ftype)
            move_clauses.append("MOVE ? TO ?")
            move_params.extend([logical, physical])

        move_sql = ", ".join(move_clauses)

        # مهم جداً: نُغلق كل اتصالات SQLAlchemy pool طوعاً قبل العزل.
        # وإلا فإن SET SINGLE_USER WITH ROLLBACK IMMEDIATE سيقتل اتصالات الـ pool
        # فجأة، فتبقى في الـ pool كاتصالات ميتة (stale) ويفشل أي استخدام لاحق لها
        # — بما في ذلك إنهاء رد هذا الطلب نفسه (يظهر ERR_CONTENT_LENGTH_MISMATCH
        # في المتصفح). بعد dispose سيُنشئ SQLAlchemy اتصالات جديدة عند الحاجة.
        try:
            db.engine.dispose()
        except Exception as exc:
            current_app.logger.warning(f"[RESTORE] couldn't dispose engine pool: {exc}")

        # 1) عزل القاعدة لطرد الاتصالات (فقط إن كانت موجودة)
        if existing_paths:
            try:
                cursor.execute(
                    f"ALTER DATABASE [{db_name_raw}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE"
                )
            except Exception as exc:
                current_app.logger.warning(
                    f"[RESTORE] couldn't set SINGLE_USER (may be fine if db absent): {exc}"
                )

        # 2) تنفيذ RESTORE — اسم القاعدة لا يمكن تمريره كـ parameter (DDL)،
        #    لكنه مُتحقَّق منه بـ regex مسبقاً. المسارات تُمرَّر كـ parameters.
        try:
            cursor.execute(
                f"RESTORE DATABASE [{db_name_raw}] FROM DISK = ? "
                f"WITH REPLACE, RECOVERY, {move_sql}",
                ([sql_path] + move_params),
            )
            # استهلاك أي result sets (رسائل progress) حتى يكتمل RESTORE
            try:
                while cursor.nextset():
                    pass
            except Exception:
                pass
        except Exception as exc:
            # في حال فشل الاستعادة نحاول إعادة القاعدة لوضع متعدد المستخدمين
            try:
                cursor.execute(
                    f"ALTER DATABASE [{db_name_raw}] SET MULTI_USER"
                )
            except Exception:
                pass
            return f"فشل تنفيذ RESTORE DATABASE: {exc}"

        # 3) إعادة القاعدة لوضع MULTI_USER
        try:
            cursor.execute(f"ALTER DATABASE [{db_name_raw}] SET MULTI_USER")
        except Exception as exc:
            current_app.logger.warning(f"[RESTORE] couldn't set MULTI_USER: {exc}")

        cursor.close()
    finally:
        raw_conn.close()

    # نظافة نهائية للـ pool: نضمن أن أي اتصال قديم تم التخلص منه، فالطلبات
    # اللاحقة تفتح اتصالات جديدة على القاعدة المُستعادة.
    try:
        db.engine.dispose()
    except Exception as exc:
        current_app.logger.warning(f"[RESTORE] couldn't dispose engine pool (post): {exc}")

    return None


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


@backup_bp.route('/database/restore', methods=['POST'])
@token_required
def restore_database_backup(user):
    """
    استعادة قاعدة البيانات من ملف .bak يرفعه المستخدم (multipart/form-data،
    الحقل: file). مقتصر على super_admin. العملية تستبدل القاعدة الحالية بالكامل
    وتطرد جميع الاتصالات الأخرى أثناء التنفيذ.

    الفكرة (معاكسة لـ backup):
      1) Flask يحفظ الملف المرفوع في flask_dir.
      2) SQL Server يقرأ نفس الملف من sql_dir (نفس volume) وينفّذ RESTORE.
      3) Flask يحذف الملف بعد الانتهاء.
    """
    if not user.is_super_admin():
        return jsonify({'message': 'غير مصرح — هذه العملية لـ super_admin فقط'}), 403

    # ملف الـ .bak أكبر بكثير من الحد العام (MAX_CONTENT_LENGTH=16MB).
    # نرفع الحد لهذا الـ request فقط قبل أي قراءة لـ request.files (القراءة
    # كسولة، فتعيين الحد الآن يُطبَّق عند parsing الـ multipart body).
    # القيمة قابلة للضبط عبر RESTORE_MAX_CONTENT_LENGTH (بايت)، الافتراضي 5GB.
    try:
        restore_limit = int(
            os.environ.get('RESTORE_MAX_CONTENT_LENGTH')
            or current_app.config.get('RESTORE_MAX_CONTENT_LENGTH')
            or (5 * 1024 * 1024 * 1024)
        )
        request.max_content_length = restore_limit
    except Exception as exc:
        current_app.logger.warning(f"[RESTORE] couldn't raise max_content_length: {exc}")

    if 'file' not in request.files:
        return jsonify({'message': 'لم يتم إرفاق ملف النسخة الاحتياطية (الحقل: file)'}), 400

    upload = request.files['file']
    if not upload or upload.filename == '':
        return jsonify({'message': 'اسم الملف فارغ'}), 400

    original_name = secure_filename(upload.filename)
    if not original_name.lower().endswith('.bak'):
        return jsonify({'message': 'صيغة الملف غير مدعومة — يجب أن يكون ملف .bak'}), 400

    db_name_raw = _extract_db_name()
    if not db_name_raw:
        return jsonify({'message': 'تعذّر تحديد اسم قاعدة البيانات'}), 500

    # حماية ضد SQL injection (لا يمكن parameter binding مع DDL)
    if not re.match(r'^[A-Za-z0-9_\-]+$', db_name_raw):
        return jsonify({'message': 'اسم قاعدة البيانات يحوي رموزاً غير مدعومة'}), 500

    cfg = _get_config()
    flask_dir = cfg['flask_dir']
    sql_dir = cfg['sql_dir'].rstrip('/').rstrip('\\')

    # نتأكد أن Flask يستطيع الكتابة في المجلد المشترك
    try:
        os.makedirs(flask_dir, exist_ok=True)
    except Exception as exc:
        return jsonify({
            'message': 'فشل استعادة النسخة الاحتياطية',
            'error': f"تعذّر إنشاء/الوصول لمجلد النسخ الاحتياطي: {flask_dir} ({exc})",
        }), 500

    # اسم ملف مؤقت فريد لتفادي التصادم
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_db_name = _safe_filename_component(db_name_raw)
    file_name = f"restore_{safe_db_name}_{timestamp}.bak"
    flask_path = os.path.join(flask_dir, file_name)

    # المسار كما يراه SQL Server
    if '/' in sql_dir or cfg['mode'] == 'shared':
        sql_path = f"{sql_dir}/{file_name}"
    else:
        sql_path = os.path.join(sql_dir, file_name)

    current_app.logger.info(
        f"[RESTORE] mode={cfg['mode']} user={user.id} db={db_name_raw} "
        f"flask_path={flask_path} sql_path={sql_path}"
    )

    # 1) حفظ الملف المرفوع
    try:
        upload.save(flask_path)
    except Exception as exc:
        _delete_file_silent(flask_path)
        return jsonify({
            'message': 'فشل استعادة النسخة الاحتياطية',
            'error': f"تعذّر حفظ الملف المرفوع: {exc}",
        }), 500

    # 2) تنفيذ RESTORE
    error = _run_restore(db_name_raw, sql_path)

    # 3) حذف الملف المؤقت في كل الأحوال
    _delete_file_silent(flask_path)

    if error:
        current_app.logger.error(f"[RESTORE] {error}")
        return jsonify({
            'message': 'فشل استعادة النسخة الاحتياطية',
            'error': error,
            'mode': cfg['mode'],
            'hint': (
                'في shared mode تأكد أن نفس volume mounted في كلٍ من SQL Server '
                'و Flask containers. تأكد أيضاً أن الملف نسخة .bak صالحة لنفس '
                'قاعدة البيانات، وأن لا توجد عمليات أخرى تستخدم القاعدة.'
            ),
        }), 500

    current_app.logger.info(f"[RESTORE] success db={db_name_raw}")
    return jsonify({
        'message': 'تمت استعادة قاعدة البيانات بنجاح',
        'database_name': db_name_raw,
    }), 200
