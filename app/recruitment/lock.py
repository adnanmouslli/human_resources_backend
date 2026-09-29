# app/recruitment/lock.py
# قفل قسم التوظيف بكلمة مرور يحددها المدير العام
#
# الآلية:
#   1. المستخدم يُدخل كلمة المرور → POST /api/recruitment-lock/unlock → رمز فتح (JWT قصير العمر)
#   2. الواجهة ترسل الرمز في الترويسة X-Recruitment-Unlock مع كل طلب إلى /api/recruitment/...
#   3. أثناء النشاط تجدد الواجهة الرمز عبر /refresh، وعند الخمول ينتهي الرمز → يُطلب كلمة المرور مجدداً
#   4. أي طلب إلى /api/recruitment/... بدون رمز صالح يُرفض بالحالة 423 (Locked)

import time
import datetime

import jwt
from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash

from app import db
from app.utils import token_required, verify_token
from app.recruitment.models import RecruitmentLockSettings

recruitment_lock_bp = Blueprint('recruitment_lock', __name__, url_prefix='/api/recruitment-lock')

UNLOCK_HEADER = 'X-Recruitment-Unlock'
TOKEN_TYPE = 'recruitment_unlock'

MIN_TIMEOUT_MINUTES = 1
MAX_TIMEOUT_MINUTES = 240
MIN_PASSWORD_LENGTH = 4
# مهلة سماح فوق مدة الخمول: الواجهة تقفل بدقة عند انتهاء المدة، والخادم يتسامح قليلاً
# حتى لا ينتهي الرمز بين تجديدين (الواجهة تجدد كل 45 ثانية أثناء النشاط)
TOKEN_GRACE_SECONDS = 60

# حماية من التخمين: عدد المحاولات الفاشلة المسموح بها خلال نافذة زمنية
MAX_FAILED_ATTEMPTS = 5
FAILED_WINDOW_SECONDS = 5 * 60
_failed_attempts = {}  # user_id -> [timestamps]


# ─────────────────────────────────────────────────────────────────────
# مساعدات
# ─────────────────────────────────────────────────────────────────────

def _issue_unlock_token(user_id, settings):
    payload = {
        'typ': TOKEN_TYPE,
        'user_id': user_id,
        'ver': settings.lock_version,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(
            minutes=settings.idle_timeout_minutes, seconds=TOKEN_GRACE_SECONDS
        ),
    }
    return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')


def _is_valid_unlock_token(token, user_id, settings):
    if not token:
        return False
    try:
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
    except Exception:
        return False
    return (
        payload.get('typ') == TOKEN_TYPE
        and payload.get('user_id') == user_id
        and payload.get('ver') == settings.lock_version
    )


def _token_response(user_id, settings):
    return {
        'unlock_token': _issue_unlock_token(user_id, settings),
        'idle_timeout_minutes': settings.idle_timeout_minutes,
    }


def _recent_failures(user_id):
    now = time.time()
    attempts = [t for t in _failed_attempts.get(user_id, []) if now - t < FAILED_WINDOW_SECONDS]
    _failed_attempts[user_id] = attempts
    return attempts


def enforce_recruitment_lock():
    """
    before_request لـ recruitment_bp: يمنع الوصول لأي نقطة نهاية للتوظيف
    ما لم يكن مع الطلب رمز فتح صالح (عند تفعيل القفل).
    """
    if request.method == 'OPTIONS':
        return None

    settings = RecruitmentLockSettings.get()
    if not settings.is_active_lock:
        return None

    # التحقق من هوية المستخدم يتم لاحقاً عبر token_required؛ هنا نحتاج فقط user_id
    auth_header = request.headers.get('Authorization', '')
    parts = auth_header.split(' ')
    payload = verify_token(parts[1]) if len(parts) == 2 else None
    if not payload:
        return None  # سيُرفض الطلب بـ 401 من token_required

    if _is_valid_unlock_token(request.headers.get(UNLOCK_HEADER), payload.get('user_id'), settings):
        return None

    return jsonify({
        'message': 'قسم التوظيف مقفل، يرجى إدخال كلمة المرور',
        'code': 'RECRUITMENT_LOCKED',
    }), 423


# ─────────────────────────────────────────────────────────────────────
# نقاط النهاية للمستخدمين
# ─────────────────────────────────────────────────────────────────────

@recruitment_lock_bp.route('/status', methods=['GET'])
@token_required
def get_lock_status(user):
    """هل قسم التوظيف مقفل؟ وما مدة الخمول؟"""
    settings = RecruitmentLockSettings.get()
    return jsonify({
        'is_enabled': settings.is_active_lock,
        'idle_timeout_minutes': settings.idle_timeout_minutes,
    }), 200


@recruitment_lock_bp.route('/unlock', methods=['POST'])
@token_required
def unlock(user):
    """فتح قسم التوظيف بكلمة المرور"""
    settings = RecruitmentLockSettings.get()
    if not settings.is_active_lock:
        return jsonify(_token_response(user.id, settings)), 200

    if len(_recent_failures(user.id)) >= MAX_FAILED_ATTEMPTS:
        return jsonify({'message': 'محاولات كثيرة خاطئة، يرجى المحاولة بعد بضع دقائق'}), 429

    password = (request.get_json(silent=True) or {}).get('password') or ''
    if not check_password_hash(settings.password_hash, password):
        _failed_attempts.setdefault(user.id, []).append(time.time())
        # 400 وليس 401 حتى لا يعتبرها الـ interceptor انتهاء جلسة الدخول
        return jsonify({'message': 'كلمة المرور غير صحيحة'}), 400

    _failed_attempts.pop(user.id, None)
    return jsonify(_token_response(user.id, settings)), 200


@recruitment_lock_bp.route('/refresh', methods=['POST'])
@token_required
def refresh(user):
    """تجديد رمز الفتح أثناء نشاط المستخدم"""
    settings = RecruitmentLockSettings.get()
    if settings.is_active_lock and not _is_valid_unlock_token(
        request.headers.get(UNLOCK_HEADER), user.id, settings
    ):
        return jsonify({'message': 'انتهت الجلسة، يرجى إدخال كلمة المرور', 'code': 'RECRUITMENT_LOCKED'}), 423
    return jsonify(_token_response(user.id, settings)), 200


# ─────────────────────────────────────────────────────────────────────
# إعدادات القفل (المدير العام فقط)
# ─────────────────────────────────────────────────────────────────────

@recruitment_lock_bp.route('/settings', methods=['GET'])
@token_required
def get_lock_settings(user):
    if not user.is_super_admin():
        return jsonify({'message': 'غير مصرح'}), 403
    return jsonify(RecruitmentLockSettings.get().to_dict()), 200


@recruitment_lock_bp.route('/settings', methods=['PUT'])
@token_required
def update_lock_settings(user):
    if not user.is_super_admin():
        return jsonify({'message': 'يُسمح للمدير العام فقط بتعديل الإعدادات'}), 403

    settings = RecruitmentLockSettings.get()
    data = request.get_json(silent=True) or {}

    if 'idle_timeout_minutes' in data:
        try:
            timeout = int(data['idle_timeout_minutes'])
        except (TypeError, ValueError):
            return jsonify({'message': 'مدة الخمول يجب أن تكون رقماً صحيحاً'}), 400
        if not MIN_TIMEOUT_MINUTES <= timeout <= MAX_TIMEOUT_MINUTES:
            return jsonify({
                'message': f'مدة الخمول يجب أن تكون بين {MIN_TIMEOUT_MINUTES} و {MAX_TIMEOUT_MINUTES} دقيقة'
            }), 400
        settings.idle_timeout_minutes = timeout

    new_password = data.get('new_password')
    if new_password:
        if len(new_password) < MIN_PASSWORD_LENGTH:
            return jsonify({'message': f'كلمة المرور يجب ألا تقل عن {MIN_PASSWORD_LENGTH} أحرف'}), 400
        settings.password_hash = generate_password_hash(new_password)
        settings.lock_version = (settings.lock_version or 0) + 1

    if 'is_enabled' in data:
        enable = bool(data['is_enabled'])
        if enable and not settings.password_hash:
            return jsonify({'message': 'يجب تعيين كلمة مرور قبل تفعيل القفل'}), 400
        if enable and not settings.is_enabled:
            settings.lock_version = (settings.lock_version or 0) + 1
        settings.is_enabled = enable

    settings.updated_by = user.id
    db.session.commit()
    _failed_attempts.clear()
    return jsonify(settings.to_dict()), 200
