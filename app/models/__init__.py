# app/models/__init__.py

# استيراد الكائن db من التطبيق الرئيسي
from app import db  

# استيراد جميع الموديلات التي تم تعديلها أو إضافتها
from .user import User
from .employee import Employee
from .job_title import JobTitle
from .shift import Shift
from .profession import Profession
from .attendance import Attendance  # استيراد جدول Attendance
from .advance import Advance
from .production_piece import ProductionPiece
from .production_monitoring import ProductionMonitoring
from .monthly_attendance import MonthlyAttendance

# استيراد Enum و AttendanceType من ملف attendance_type.py
from .attendance_type import AttendanceType, AttendanceTypeEnum  # استيراد الـ Enum و AttendanceType

# استيراد ملف العلاقات بين الجداول (relationships)
from .relationships import *  # استيراد جميع العلاقات بين الجداول
