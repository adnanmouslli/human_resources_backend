# app/models/relationships.py

from app import db
from .employee import Employee
from .job_title import JobTitle
from .profession import Profession
from .attendance import Attendance
from .advance import Advance
from .monthly_attendance import MonthlyAttendance
from .production_monitoring import ProductionMonitoring
from .production_piece import ProductionPiece

# ========== Employee relationships ==========
Employee.job_title = db.relationship('JobTitle', backref='employees', lazy=True)
Employee.profession = db.relationship('Profession', backref='employees', lazy=True)

# ========== Attendance relationships ==========
Attendance.employee = db.relationship('Employee', backref='attendances', lazy=True)
# Attendance.attendance_type ← تم حذفه لأنه لم يعد هناك علاقة

# ========== Advance relationships ==========
Advance.employee = db.relationship('Employee', backref='advances', lazy=True)

# ========== MonthlyAttendance relationships ==========
MonthlyAttendance.employee = db.relationship('Employee', backref='monthly_attendance', lazy=True)

# ========== ProductionMonitoring relationships ==========
ProductionMonitoring.employee = db.relationship('Employee', backref='production_monitoring', lazy=True)
ProductionMonitoring.piece = db.relationship('ProductionPiece', backref='production_monitoring', lazy=True)
