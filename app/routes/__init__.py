# app/routes/__init__.py

from app.routes.auth import auth_routes
from app.routes.protected import protected_routes
from app.routes.employee import employee_bp
from app.routes.attendance import attendance_bp
from app.routes.advance import advances_bp
from app.routes.productionPiece import production_piece_bp
from app.routes.ProductionMonitoring import production_monitoring_bp
from app.routes.profession import profession_bp
from app.routes.MonthlyAttendance import monthly_attendance_bp
from app.routes.payroll import payroll_bp
from app.routes.reward import rewards_bp  
from app.routes.penalty import penalties_bp  