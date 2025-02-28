# دليل إعداد وتشغيل مشروع Flask

## المتطلبات الأساسية
- Python 3.12.2
- pip 24.0 أو أحدث
- Git (للتحكم بالإصدارات)

## 1. إعداد البيئة الافتراضية
```bash
# إنشاء البيئة الافتراضية
python3 -m venv venv

# تفعيل البيئة الافتراضية
# في Linux/macOS
source venv/bin/activate
# في Windows
venv\Scripts\activate

# تحديث pip
python -m pip install --upgrade pip
```

## 2. تثبيت المتطلبات
```bash
# تثبيت المكتبات المطلوبة
pip install -r requirements.txt

# في حال واجهت مشاكل في التثبيت، جرب:
pip install --no-cache-dir -r requirements.txt
```

## 3. إعداد قاعدة البيانات وملفات الترحيل

### حذف ملفات الترحيل القديمة (إذا وجدت)
```bash
# حذف مجلد الترحيلات القديم
rm -rf migrations/
```

### إنشاء وتنفيذ الترحيلات
```bash
# تهيئة نظام الترحيلات
flask db init

# إنشاء ملف الترحيل
flask db migrate -m "Initial migration"

# تطبيق الترحيلات
flask db upgrade
```

## 4. إعداد ملف البيئة (.env)
قم بإنشاء ملف `.env` في المجلد الرئيسي للمشروع:
```ini
# إعدادات قاعدة البيانات
DATABASE_URL=your_database_connection_string
SECRET_KEY=your_secret_key

# إعدادات Flask
FLASK_APP=app
FLASK_ENV=development
FLASK_DEBUG=1
```

## 5. تشغيل المشروع

### للتطوير المحلي
```bash
# تشغيل المشروع في وضع التطوير
flask run --host=0.0.0.0 --port=3000
```

### للإنتاج باستخدام Gunicorn
```bash
gunicorn --bind 0.0.0.0:3000 --worker-class gevent --workers 4 "app:create_app()"
```

## 6. التشغيل باستخدام Docker

### بناء وتشغيل الحاوية
```bash
# بناء صورة Docker
docker build -t flask-project .

# تشغيل الحاوية
docker run -d -p 3000:3000 --name flask-app flask-project
```

### باستخدام Docker Compose
```bash
# تشغيل المشروع
docker-compose up -d

# إيقاف المشروع
docker-compose down
```

## ملاحظات هامة
1. تأكد من تفعيل البيئة الافتراضية قبل تنفيذ أي أوامر
2. احتفظ بنسخة احتياطية من قاعدة البيانات قبل تنفيذ الترحيلات
3. في بيئة الإنتاج، تأكد من تغيير إعدادات البيئة المناسبة
4. راجع ملف requirements.txt بشكل دوري للتحديثات الأمنية

## حل المشاكل الشائعة

### مشاكل تثبيت المكتبات
```bash
# مسح ذاكرة التخزين المؤقت لـ pip
pip cache purge
pip install -r requirements.txt
```

### مشاكل الترحيلات
```bash
# إعادة تهيئة قاعدة البيانات
flask db stamp head
flask db migrate
flask db upgrade
```

### مشاكل الاتصال بقاعدة البيانات
- تأكد من صحة متغيرات البيئة
- تحقق من اتصال قاعدة البيانات
- راجع سجلات الخطأ للتفاصيل

## روابط مفيدة
- [توثيق Flask](https://flask.palletsprojects.com/)
- [توثيق Flask-SQLAlchemy](https://flask-sqlalchemy.palletsprojects.com/)
- [توثيق Flask-Migrate](https://flask-migrate.readthedocs.io/)‣畨慭彮敲潳牵散彳慢正湥੤‣畨慭彮敲潳牵散彳慢正湥੤