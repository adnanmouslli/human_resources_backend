import os
from app import create_app, db
from flask_cors import CORS

# تحديد بيئة التشغيل من متغيرات البيئة
env = os.environ.get('FLASK_ENV', 'development')

# إنشاء التطبيق مع الإعدادات المناسبة
app = create_app(env)

# تكوين CORS
CORS(app)

# طباعة معلومات حول المستأجر وقاعدة البيانات
print(f"بدء تشغيل التطبيق للمستأجر: {app.config.get('TENANT_ID', 'default')}")
print(f"قاعدة البيانات: {app.config.get('DB_NAME', 'hr_production')}")
print(f"بيئة التشغيل: {env}")

if __name__ == '__main__':
    # إنشاء جداول قاعدة البيانات إذا لم تكن موجودة
    with app.app_context():
        db.create_all()
    
    # تشغيل التطبيق
    app.run(host='0.0.0.0', port=3000, debug=(env == 'development'))