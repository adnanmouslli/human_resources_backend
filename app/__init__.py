import os
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

    # Register CLI commands (Moved after db init to avoid circular imports)
    from app.commands import (
        reset_db,
        init_db,
        fix_migrations,
        clean_migrations,
        fresh_migrate,
        show_tables,
        clear_table,
        seed_db,
        check_connection,
        test_users
    )

    app.cli.add_command(reset_db)
    app.cli.add_command(init_db)
    app.cli.add_command(fix_migrations)
    app.cli.add_command(clean_migrations)
    app.cli.add_command(fresh_migrate)
    app.cli.add_command(show_tables)
    app.cli.add_command(clear_table)
    app.cli.add_command(seed_db)
    app.cli.add_command(check_connection)
    app.cli.add_command(test_users)

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
    from app.routes.reward import rewards_bp
    from app.routes.penalty import penalties_bp
    from app.routes.branch_dept import branch_dept_bp
    # from app.routes.reports import reports_bp
    from app.routes.user import user_bp
    from app.routes.absence_transaction import absence_transaction_bp
    from app.routes.absence_answer import absence_answer_bp
    from app.routes.absence_question import absence_question_bp
    from app.routes.holiday import holiday_bp
    from app.routes.transaction_routes import transaction_bp
    from app.routes.leave_routes import leave_bp

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
    app.register_blueprint(branch_dept_bp)
    # app.register_blueprint(reports_bp)    
    app.register_blueprint(user_bp)
    app.register_blueprint(absence_transaction_bp)
    app.register_blueprint(absence_answer_bp)
    app.register_blueprint(absence_question_bp)
    app.register_blueprint(holiday_bp)
    app.register_blueprint(transaction_bp)
    app.register_blueprint(leave_bp)





    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

    return app