# app/services/push_service.py
# إرسال الإشعارات الفورية (Push) لتطبيق الجوال عبر Firebase Cloud Messaging

import logging
import os
from datetime import datetime
from typing import Dict, Optional

from app import db
from app.models.notification import DeviceToken

logger = logging.getLogger(__name__)

# مسار ملف حساب الخدمة: متغير البيئة FIREBASE_CREDENTIALS أو الملف الافتراضي في جذر المشروع
_DEFAULT_CREDENTIALS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'firebase-service-account.json',
)

_firebase_app = None
_init_failed = False


def _get_firebase_app():
    """تهيئة Firebase Admin مرة واحدة. يُرجع None إذا لم تكن الإعدادات متوفرة."""
    global _firebase_app, _init_failed
    if _firebase_app is not None or _init_failed:
        return _firebase_app

    cred_path = os.environ.get('FIREBASE_CREDENTIALS', _DEFAULT_CREDENTIALS)
    if not os.path.exists(cred_path):
        logger.warning('Firebase: ملف حساب الخدمة غير موجود (%s) - الإشعارات الفورية معطلة', cred_path)
        _init_failed = True
        return None

    try:
        import firebase_admin
        from firebase_admin import credentials

        # مهلة قصيرة حتى لا يتعطل الطلب إذا كان Firebase بطيئاً (الافتراضي 120 ثانية)
        _firebase_app = firebase_admin.initialize_app(
            credentials.Certificate(cred_path),
            {'httpTimeout': 5},
        )
    except Exception as e:
        logger.error('Firebase: فشل التهيئة: %s', e)
        _init_failed = True
    return _firebase_app


class PushService:

    @staticmethod
    def ensure_table():
        """إنشاء جدول device_tokens إذا لم يكن موجوداً (آمن للتكرار)."""
        DeviceToken.__table__.create(bind=db.engine, checkfirst=True)

    @staticmethod
    def register_token(user_id: int, token: str, platform: Optional[str] = None) -> DeviceToken:
        """حفظ رمز الجهاز للمستخدم. إذا كان الرمز لمستخدم آخر (نفس الجهاز) يُنقل للمستخدم الحالي."""
        device = DeviceToken.query.filter_by(token=token).first()
        if device:
            device.user_id = user_id
            device.platform = platform or device.platform
            device.updated_at = datetime.now()
        else:
            device = DeviceToken(user_id=user_id, token=token, platform=platform)
            db.session.add(device)
        db.session.commit()
        return device

    @staticmethod
    def unregister_token(token: str, user_id: Optional[int] = None) -> bool:
        q = DeviceToken.query.filter_by(token=token)
        if user_id is not None:
            q = q.filter_by(user_id=user_id)
        deleted = q.delete()
        db.session.commit()
        return deleted > 0

    @staticmethod
    def send_to_user(user_id: int, title: str, body: str, data: Optional[Dict] = None) -> int:
        """
        إرسال إشعار فوري لكل أجهزة المستخدم.
        يُرجع عدد الأجهزة التي وصلها الإشعار. لا يرمي استثناءات أبداً.
        """
        try:
            app = _get_firebase_app()
            if app is None:
                return 0

            tokens = [d.token for d in DeviceToken.query.filter_by(user_id=user_id).all()]
            if not tokens:
                return 0

            from firebase_admin import messaging

            # قيم data في FCM يجب أن تكون نصوصاً
            str_data = {k: str(v) for k, v in (data or {}).items() if v is not None}

            message = messaging.MulticastMessage(
                tokens=tokens,
                notification=messaging.Notification(title=title, body=body),
                data=str_data,
                android=messaging.AndroidConfig(
                    priority='high',
                    notification=messaging.AndroidNotification(
                        channel_id='hr_notifications',
                        sound='default',
                    ),
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(aps=messaging.Aps(sound='default')),
                ),
            )
            response = messaging.send_each_for_multicast(message, app=app)

            # حذف الرموز المنتهية أو غير الصالحة
            invalid = []
            for token, res in zip(tokens, response.responses):
                if not res.success and isinstance(
                    res.exception,
                    (messaging.UnregisteredError, messaging.SenderIdMismatchError),
                ):
                    invalid.append(token)
            if invalid:
                DeviceToken.query.filter(DeviceToken.token.in_(invalid)).delete(synchronize_session=False)
                db.session.commit()

            return response.success_count
        except Exception as e:
            db.session.rollback()
            logger.error('Firebase: فشل إرسال الإشعار للمستخدم %s: %s', user_id, e)
            return 0
