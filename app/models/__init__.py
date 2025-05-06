# app/models/__init__.py

from app import db

from .user import User
from .branch import Branch 
from .department import Department 
from .department import BranchDepartment
from .employee import Employee
from .job_title import JobTitle
from .shift import Shift
from .profession import Profession
from .attendance import Attendance
from .advance import Advance
from .production_piece import ProductionPiece
from .production_monitoring import ProductionMonitoring
from .monthly_attendance import MonthlyAttendance
from .reward import Reward  # إضافة مودل المكافآت
from .penalty import Penalty  # إضافة مودل الجزاءات


from .relationships import *