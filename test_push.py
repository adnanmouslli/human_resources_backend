"""
اختبار الإشعارات الفورية (Firebase) من السيرفر.

الاستخدام:
    venv/bin/python test_push.py <username>

يتحقق من: تحميل مفتاح Firebase، ووجود أجهزة مسجلة للمستخدم، ثم يرسل إشعار تجريبي.
"""

import sys

from app import create_app


def main():
    if len(sys.argv) < 2:
        print('الاستخدام: python test_push.py <username>')
        sys.exit(1)

    username = sys.argv[1]
    app = create_app()

    with app.app_context():
        from app.models.notification import DeviceToken
        from app.models.user import User
        from app.services.push_service import PushService, _get_firebase_app

        # 1. مفتاح Firebase
        if _get_firebase_app() is None:
            print('❌ Firebase غير مهيأ: تأكد من وجود firebase-service-account.json في جذر المشروع')
            sys.exit(1)
        print('✅ Firebase مهيأ بنجاح')

        # 2. المستخدم وأجهزته
        user = User.query.filter_by(username=username).first()
        if not user:
            print(f'❌ المستخدم "{username}" غير موجود')
            sys.exit(1)

        devices = DeviceToken.query.filter_by(user_id=user.id).all()
        print(f'👤 {username} ({user.user_type}) - أجهزة مسجلة: {len(devices)}')
        for d in devices:
            print(f'   - {d.platform or "?"} | آخر تحديث {d.updated_at}')

        if not devices:
            print('❌ لا توجد أجهزة: سجّل دخول بهذا الحساب من التطبيق أولاً ووافق على صلاحية الإشعارات')
            sys.exit(1)

        # 3. إرسال إشعار تجريبي
        sent = PushService.send_to_user(
            user.id,
            'اختبار الإشعارات',
            'إذا وصلك هذا الإشعار فالنظام يعمل بشكل صحيح ✅',
            data={'type': 'system'},
        )
        if sent:
            print(f'✅ تم الإرسال بنجاح إلى {sent} جهاز - تحقق من الجوال')
        else:
            print('❌ فشل الإرسال - راجع سجلات السيرفر (pm2 logs flask-app)')
            sys.exit(1)


if __name__ == '__main__':
    main()
