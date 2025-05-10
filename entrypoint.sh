#!/bin/bash
set -e

# انتظار حتى تكون قاعدة البيانات جاهزة
echo "انتظار جاهزية قاعدة البيانات..."
for i in {1..30}; do
    python -c "import pyodbc; pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=hr_sqlserver;DATABASE=master;UID=sa;PWD=SQL@123456789')" && break
    echo "محاولة الاتصال بقاعدة البيانات... محاولة $i من 30"
    sleep 2
done

# التحقق من نجاح الاتصال
if [ $i -eq 30 ]; then
    echo "فشل الاتصال بقاعدة البيانات بعد 30 محاولة. إنهاء."
    exit 1
fi

echo "تم الاتصال بقاعدة البيانات بنجاح!"

# إذا كان FLASK_MIGRATE=1، قم بتنفيذ التهجير
if [ "$FLASK_MIGRATE" = "1" ]; then
    echo "بدء عملية التهجير..."
    python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"
    if [ -d "migrations" ]; then
        flask db upgrade
    else
        flask db init
        flask db migrate -m "Initial migration"
        flask db upgrade
    fi
    echo "اكتملت عملية التهجير بنجاح!"
fi

# تنفيذ الأمر المحدد (الافتراضي: تشغيل التطبيق)
exec "$@"
