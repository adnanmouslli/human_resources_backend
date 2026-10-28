# قالب ملف الإعدادات — انسخه إلى app/config.py (الملف الحقيقي في .gitignore) وعدّل القيم لكل بيئة
import os
from urllib.parse import quote_plus

class Config:
    DB_SERVER   = os.environ.get('DB_SERVER',   'localhost')
    DB_PORT     = os.environ.get('DB_PORT',     '1433')
    DB_NAME     = os.environ.get('DB_NAME',     'hr_db')
    DB_USER     = os.environ.get('DB_USER',     'sa')
    DB_PASSWORD = quote_plus(os.environ.get('DB_PASSWORD', 'change-me'))

    SQLALCHEMY_DATABASE_URI = (
        f"mssql+pyodbc://{DB_USER}:{DB_PASSWORD}@{DB_SERVER},{DB_PORT}/{DB_NAME}"
        "?driver=ODBC+Driver+17+for+SQL+Server"
        "&Connection+Timeout=30"
        "&TrustServerCertificate=yes"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_AS_ASCII = False

    # يوقّع توكنات الدخول (JWT) — يجب أن يكون عشوائياً وطويلاً في كل سيرفر:
    #   python -c "import secrets; print(secrets.token_hex(32))"
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me')

    # إعدادات التشغيل (يقرؤها run.py، ويمكن تجاوزها بمتغيرات بيئة بنفس الاسم)
    HOST = '0.0.0.0'
    PORT = 5000                # السيرفر: المنفذ الخاص بالزبون
    DEBUG = False              # True في اللوكال فقط — لا تفعّله على السيرفر أبداً
    CREATE_SUPER_ADMIN = False
