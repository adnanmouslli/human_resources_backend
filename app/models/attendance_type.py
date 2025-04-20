# app/models/attendance_type.py

import enum
from sqlalchemy import Enum
from app import db

class AttendanceTypeEnum(enum.Enum):
    PRESENT = "present"        # حاضر
    ABSENT = "absent"          # غائب
    LATE = "late"              # متأخر
    EXCUSED = "excused"        # بعذر
    VACATION = "vacation"      # إجازة
    HOLIDAY = "holiday"        # عطلة
    SICK = "sick"              # مرضي

class AttendanceType(db.Model):
    __tablename__ = 'attendance_types'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(Enum(AttendanceTypeEnum), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=True)

    def __repr__(self):
        return f"<AttendanceType {self.name.name}>"
