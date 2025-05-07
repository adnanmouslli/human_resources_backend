#!/bin/bash

# هذا السكريبت يقوم بتشغيل تطبيق Flask وربطه بـ SQL Server

# التأكد من وجود ملف config.py للاتصال بقاعدة البيانات
if [ ! -f "app/config.py" ]; then
    echo "إنشاء ملف config.py..."
    mkdir -p app
    cat > app/config.py << EOL
class Config:
    # معلومات قاعدة البيانات
    SERVER = 'hr_sqlserver'  # اسم حاوية SQL Server
    DATABASE = 'hr1'  # اسم قاعدة البيانات الأولى
    USERNAME = 'sa'  # اسم المستخدم
    PASSWORD = 'SQL@123456789'  # كلمة المرور
    
    # سلسلة اتصال SQL Server باستخدام pyodbc
    SQLALCHEMY_DATABASE_URI = f"mssql+pyodbc://{USERNAME}:{PASSWORD}@{SERVER}:1433/{DATABASE}?driver=ODBC+Driver+17+for+SQL+Server&timeout=60"
    
    # إعدادات إضافية
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_AS_ASCII = False
    
    # إعدادات التحميل
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    
    # يمكنك إضافة أي إعدادات أخرى هنا
    DEBUG = True
    PORT = 3000  # المنفذ (يمكن تغييره لكل نسخة)
EOL
    echo "تم إنشاء ملف config.py بنجاح."
fi

# التحقق من وجود SQL Server
# if ! docker ps | grep -q hr_sqlserver; then
#     echo "حاوية SQL Server غير قيد التشغيل. جاري تشغيلها..."
#     if docker ps -a | grep -q hr_sqlserver; then
#         docker start hr_sqlserver
#     else
#         echo "حاوية SQL Server غير موجودة. تأكد من إنشائها أولاً."
#         exit 1
#     fi
    
#     # الانتظار لبدء تشغيل SQL Server
#     echo "الانتظار لمدة 30 ثانية لبدء تشغيل SQL Server..."
#     sleep 30
# fi

# إيقاف وإزالة حاوية Flask إذا كانت موجودة
# if docker ps -a | grep -q hr_flask_app; then
#     echo "إيقاف وإزالة حاوية Flask الموجودة..."
#     docker stop hr_flask_app
#     docker rm hr_flask_app
# fi

# بناء وتشغيل حاوية Flask
echo "بناء وتشغيل حاوية Flask..."
docker-compose -f docker-compose.yml up -d backend

# انتظار 10 ثوانٍ لبدء تشغيل Flask
echo "الانتظار لمدة 10 ثوانٍ لبدء تشغيل Flask..."
sleep 10

# عرض سجلات Flask
echo "سجلات Flask:"
docker logs hr_flask_app

echo "تم تشغيل تطبيق Flask وربطه بقاعدة البيانات hr1 بنجاح."
echo "يمكنك الوصول إلى التطبيق على المنفذ 3000."