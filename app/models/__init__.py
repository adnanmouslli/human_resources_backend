# app/models/__init__.py

from app import db

from .branch import Branch 
from .department import Department, BranchDepartment
from .employee import Employee
from .user import User, UserBranchHead, UserDepartmentHead
from .job_title import JobTitle
from .shift import Shift
from .profession import Profession
from .attendance import Attendance
from .attendance_type import AttendanceType
from .advance import Advance
from .production_piece import ProductionPiece
from .production_monitoring import ProductionMonitoring
from .monthly_attendance import MonthlyAttendance
from .reward import Reward  # إضافة مودل المكافآت
from .penalty import Penalty  # إضافة مودل الجزاءات
from .transaction_types import TransactionType
from .absence_transaction import AbsenceTransaction
from .transaction_history import TransactionHistory
from .absence_question import AbsenceQuestion
from .absence_answer import AbsenceAnswer
from .holiday import Holiday
from .transaction import Transaction, TransactionApproval
from .leave import Leave





from .relationships import *