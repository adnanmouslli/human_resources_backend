# app/__init__.py

import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS

# تهيئة الامتدادات
db = SQLAlchemy()
migrate = Migrate()

def create_app(config_name='default'):
    """إنشاء وتكوين تطبيق Flask"""
    app = Flask(__name__)
    
    # تحميل إعدادات التكوين
    if config_name == 'default':
        app.config.from_object('app.config.Config')
    else:
        # استخدم الإعدادات الديناميكية إذا تم تحديد اسم تكوين مختلف
        from config import config
        app.config.from_object(config[config_name])
    
    # تعطيل ترميز ASCII للـ JSON
    app.config['JSON_AS_ASCII'] = False
    
    # تكوين مجلد التحميل والحد الأقصى لحجم الملف
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 ميجابايت
    
    # تهيئة الامتدادات
    db.init_app(app)
    migrate.init_app(app, db)
    
    # تكوين CORS
    CORS(app)
    
    # تسجيل المسارات (Blueprints)
    from app.routes.auth import auth_routes
    from app.routes.employee import employee_bp
    from app.routes.shift import shift_bp
    from app.routes.jobTitle import job_title_bp
    from app.routes.attendance import attendance_bp
    from app.routes.advance import advances_bp
    from app.routes.productionPiece import production_piece_bp
    from app.routes.ProductionMonitoring import production_monitoring_bp
    from app.routes.profession import profession_bp
    from app.routes.MonthlyAttendance import monthly_attendance_bp
    from app.routes.payroll import payroll_bp
    from app.routes.reward import rewards_bp 
    from app.routes.penalty import penalties_bp  

    app.register_blueprint(auth_routes)
    app.register_blueprint(employee_bp)
    app.register_blueprint(shift_bp)
    app.register_blueprint(job_title_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(advances_bp)
    app.register_blueprint(production_piece_bp)
    app.register_blueprint(production_monitoring_bp)
    app.register_blueprint(profession_bp)
    app.register_blueprint(monthly_attendance_bp)
    app.register_blueprint(payroll_bp)
    app.register_blueprint(rewards_bp)  
    app.register_blueprint(penalties_bp) 

    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    
    return app