class Config:
    # معلومات قاعدة البيانات
    SERVER = 'hr_sqlserver'  # اسم حاوية SQL Server
    DATABASE = 'hr1'  # اسم قاعدة البيانات الأولى
    USERNAME = 'sa'  # اسم المستخدم
    PASSWORD = 'SQL@123456789'  # كلمة المرور
    
    # سلسلة اتصال SQL Server باستخدام pyodbc
    SQLALCHEMY_DATABASE_URI = "mssql+pyodbc:///?odbc_connect=DRIVER={ODBC Driver 17 for SQL Server};SERVER=hr_sqlserver;DATABASE=hr1;UID=sa;PWD=SQL@123456789"    # إعدادات إضافية
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_AS_ASCII = False
    
    # إعدادات التحميل
    # UPLOAD_FOLDER = 'uploads'
    # MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    
    # يمكنك إضافة أي إعدادات أخرى هنا
    DEBUG = True
    PORT = 3000  # المنفذ (يمكن تغييره لكل نسخة)