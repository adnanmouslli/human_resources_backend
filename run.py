import os
from app import db, create_app
from flask_cors import CORS
from app.routes.auth import create_super_admin
import socket

# إعداد timeout عام للنظام
socket.setdefaulttimeout(300)  # 5 دقائق

app = create_app()
CORS(app)

# إعدادات Flask للعمليات الطويلة
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 300
app.config['PERMANENT_SESSION_LIFETIME'] = 300

# زيادة حد الطلبات الكبيرة
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB


def setting(name, default):
    """قيمة خاصة بالبيئة: من متغيرات البيئة أولاً، ثم من app/config.py، ثم القيمة الافتراضية"""
    return os.environ.get(name, app.config.get(name, default))


def is_true(value):
    return str(value).lower() in ('1', 'true', 'yes')


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if is_true(setting('CREATE_SUPER_ADMIN', False)):
            create_super_admin()

    # المنفذ ووضع debug يختلفان بين اللوكال والسيرفر، لذلك يُقرآن من الإعدادات وليس من الكود
    app.run(
        host=setting('HOST', '0.0.0.0'),
        port=int(setting('PORT', 5000)),
        debug=is_true(setting('DEBUG', False)),
        threaded=True,
    )
