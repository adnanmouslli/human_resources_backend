import os

class Config:
    # الحصول على معرّف المستأجر من متغيرات البيئة أو استخدام القيمة الافتراضية
    TENANT_ID = os.environ.get('TENANT_ID', 'default')
    
    # استخدام اسم قاعدة البيانات من متغيرات البيئة أو استخدام القيمة الافتراضية
    DB_NAME = os.environ.get('DB_NAME', 'hr_production')
    
    # مفتاح سري للتطبيق
    SECRET_KEY = os.environ.get('SECRET_KEY', '6ad03e74cbec26ed98a94a45042409410a74aeaee427bbadb7ea64179d8e8262')
    
    # عنوان قاعدة البيانات
    SQLALCHEMY_DATABASE_URI = (
        'mssql+pyodbc:///?odbc_connect='
        'DRIVER={ODBC Driver 17 for SQL Server};'
        f'SERVER=localhost;'
        f'DATABASE={DB_NAME};'
        'UID=SA;'
        f'PWD={os.environ.get("MSSQL_SA_PASSWORD", "sql@123456789")};'
        'TrustServerCertificate=yes;'
        'Encrypt=yes;'
        'authentication=SqlPassword'
    )
    
    # تعطيل تتبع التعديلات
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # إعدادات التخزين المؤقت
    CACHE_TYPE = 'redis'
    CACHE_REDIS_HOST = 'localhost'
    CACHE_REDIS_PORT = 6379
    CACHE_REDIS_DB = 0
    CACHE_DEFAULT_TIMEOUT = 300
import os

# إعدادات التخزين المؤقت
CACHE_TYPE = 'redis'
CACHE_REDIS_HOST = 'localhost'
CACHE_REDIS_PORT = 6379
CACHE_REDIS_DB = 0
CACHE_DEFAULT_TIMEOUT = 300

class Config:
    # الحصول على معرّف المستأجر من متغيرات البيئة أو استخدام القيمة الافتراضية
    TENANT_ID = os.environ.get('TENANT_ID', 'default')
    
    # استخدام اسم قاعدة البيانات من متغيرات البيئة أو استخدام القيمة الافتراضية
    DB_NAME = os.environ.get('DB_NAME', 'hr_production')
    
    # مفتاح سري للتطبيق (يجب تغييره في الإنتاج)
    SECRET_KEY = os.environ.get('SECRET_KEY', '6ad03e74cbec26ed98a94a45042409410a74aeaee427bbadb7ea64179d8e8262')
    
    # عنوان قاعدة البيانات
    SQLALCHEMY_DATABASE_URI = (
        'mssql+pyodbc:///?odbc_connect='
        'DRIVER={ODBC Driver 17 for SQL Server};'
        f'SERVER=localhost;'
        f'DATABASE={DB_NAME};'
        'UID=SA;'
        f'PWD={os.environ.get("MSSQL_SA_PASSWORD", "sql@123456789")};'
        'TrustServerCertificate=yes;'
        'Encrypt=yes;'
        'authentication=SqlPassword'
    )
    
    # تعطيل تتبع التعديلات
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # بادئة API (اختياري، يمكن استخدامه إذا كنت تريد تغيير بادئة API)
    API_PREFIX = '/api'
    
    # إعدادات إضافية للتطبيق
    DEBUG = os.environ.get('FLASK_ENV', 'development') == 'development'
    TESTING = False
    
    # إعدادات CORS
    CORS_ORIGINS = ['*']  # يمكن تقييدها بمجال معين في الإنتاج
    
    @staticmethod
    def init_app(app):
        """تهيئة إعدادات التطبيق"""
        pass


class DevelopmentConfig(Config):
    """إعدادات بيئة التطوير"""
    DEBUG = True


class ProductionConfig(Config):
    """إعدادات بيئة الإنتاج"""
    DEBUG = False
    
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        
        # يمكن إضافة إعدادات إضافية خاصة بالإنتاج هنا


class TestingConfig(Config):
    """إعدادات بيئة الاختبار"""
    TESTING = True
    DEBUG = True
    
    # استخدام قاعدة بيانات اختبار منفصلة
    DB_NAME = 'hr_test'
    SQLALCHEMY_DATABASE_URI = (
        'mssql+pyodbc:///?odbc_connect='
        'DRIVER={ODBC Driver 17 for SQL Server};'
        f'SERVER=localhost;'
        f'DATABASE={DB_NAME};'
        'UID=SA;'
        f'PWD={os.environ.get("MSSQL_SA_PASSWORD", "sql@123456789")};'
        'TrustServerCertificate=yes;'
        'Encrypt=yes;'
        'authentication=SqlPassword'
    )


# القاموس الذي يحتوي على إعدادات التكوين المختلفة
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}# إعدادات التخزين المؤقت
CACHE_TYPE = 'redis'
CACHE_REDIS_HOST = 'localhost'
CACHE_REDIS_PORT = 6379
CACHE_REDIS_DB = 0
CACHE_DEFAULT_TIMEOUT = 300


class Config:
    SECRET_KEY = '6ad03e74cbec26ed98a94a45042409410a74aeaee427bbadb7ea64179d8e8262'
    SQLALCHEMY_DATABASE_URI = (
        'mssql+pyodbc:///?odbc_connect='
        'DRIVER={ODBC Driver 17 for SQL Server};'
        'SERVER=localhost;'
        'DATABASE=hr_production;'
        'UID=SA;'
        'PWD=sql@123456789;'
        'TrustServerCertificate=yes;'
        'Encrypt=yes;'
        'authentication=SqlPassword'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False