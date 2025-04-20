#!/bin/bash
set -e

# استخدام اسم قاعدة البيانات الديناميكي إذا تم تحديده
DB_NAME=${DB_NAME:-hr_production}

# بدء تشغيل خدمة Redis (للتخزين المؤقت)
service redis-server start

# بدء تشغيل SQL Server
/opt/mssql/bin/sqlservr &
SQLSERVER_PID=$!

# الإنتظار حتى يكون SQL Server جاهزًا
echo "بدء تشغيل SQL Server..."
for i in {1..60}; do
    if /opt/mssql-tools/bin/sqlcmd -S localhost -U SA -P "$MSSQL_SA_PASSWORD" -Q "SELECT 1" &> /dev/null; then
        echo "SQL Server جاهز."
        break
    fi
    echo "الانتظار للاتصال بـ SQL Server... محاولة $i/60"
    sleep 1
done

# إنشاء قاعدة البيانات إذا لم تكن موجودة
/opt/mssql-tools/bin/sqlcmd -S localhost -U SA -P "$MSSQL_SA_PASSWORD" -Q "IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = '$DB_NAME') BEGIN CREATE DATABASE $DB_NAME; END"
echo "تم التحقق من وجود قاعدة البيانات $DB_NAME"

# إنشاء مجلد للنسخ الاحتياطية
mkdir -p /var/opt/mssql/backup

# تحديث متغير بيئة قاعدة البيانات في ملف config.py
if [ -f "/app/config.py" ]; then
    echo "تحديث إعدادات قاعدة البيانات في config.py..."
    # نسخة احتياطية من ملف config.py
    cp /app/config.py /app/config.py.bak
    
    # تعديل اسم قاعدة البيانات في connection string
    sed -i "s/'DATABASE=hr_production;'/'DATABASE=$DB_NAME;'/g" /app/config.py
    
    echo "تم تحديث إعدادات قاعدة البيانات."
fi

# تطبيق ترحيلات قاعدة البيانات (إذا كانت موجودة)
if [ -d "/app/migrations" ]; then
    echo "تطبيق ترحيلات قاعدة البيانات..."
    cd /app
    python3 -m flask db upgrade
    echo "تم تطبيق الترحيلات بنجاح."
fi

# تشغيل تطبيق Flask
echo "بدء تشغيل تطبيق Flask..."
if [ "$FLASK_ENV" = "production" ]; then
    echo "تشغيل في وضع الإنتاج..."
    cd /app
    exec gunicorn --bind 0.0.0.0:3000 --workers 4 --timeout 120 run:app
else
    echo "تشغيل في وضع التطوير..."
    cd /app
    exec python3 run.py
fi