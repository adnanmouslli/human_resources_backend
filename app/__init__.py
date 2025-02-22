from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate() 

def create_app():
    app = Flask(__name__)
    app.config.from_object('app.config.Config')
    app.config['JSON_AS_ASCII'] = False  
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db) 

    # Register blueprints
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


    return app
