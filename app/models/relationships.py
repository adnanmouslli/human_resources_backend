from .employee import Employee
from .job_title import JobTitle
from .shift import Shift
from .profession import Profession
from .attendance import Attendance
from .advance import Advance
from .production_monitoring import ProductionMonitoring
from .production_piece import ProductionPiece
from .monthly_attendance import MonthlyAttendance

from app import db  # استيراد الكائن db من التطبيق الرئيسي

# ========== Employee relationships ========== 
Employee.job_title = db.relationship('JobTitle', backref='employees', lazy=True)
Employee.profession = db.relationship('Profession', backref='employees', lazy=True)

# ========== Attendance relationships ========== 
Attendance.employee = db.relationship('Employee', backref='attendances', lazy=True)
Attendance.attendance_type = db.relationship('AttendanceType', backref='attendances', lazy=True)  # العلاقة مع AttendanceType

# ========== Advance relationships ========== 
Advance.employee = db.relationship('Employee', backref='advances', lazy=True)

# ========== MonthlyAttendance relationships ========== 
MonthlyAttendance.employee = db.relationship('Employee', backref='monthly_attendance', lazy=True)

# ========== ProductionMonitoring relationships ========== 
ProductionMonitoring.employee = db.relationship('Employee', backref='production_monitoring', lazy=True)
ProductionMonitoring.piece = db.relationship('ProductionPiece', backref='production_monitoring', lazy=True)

# ========== AttendanceType relationships ========== 
# إذا كان لديك حاجة لعلاقات أخرى تخص AttendanceType يمكن إضافتها هنا.
# في حال احتجت إلى علاقة عكسية من نوع "many-to-one" يمكن تعديلها هنا إذا لزم الأمر.
