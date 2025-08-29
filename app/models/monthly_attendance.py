# app/models/monthly_attendance.py

from app import db
from datetime import date
from enum import Enum

# تعريف Enum داخلي خاص بأنواع الدوام
class AttendanceTypeEnum(str, Enum):
    FULL_DAY = 'full_day'      # يوم كامل
    HALF_DAY = 'half_day'      # نصف يوم
    ONLINE_DAY = 'online_day'  # يوم أونلاين
    ABSENT = 'absent'          # غائب

class MonthlyAttendance(db.Model):
    __tablename__ = 'monthly_attendance'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)

    # استخدام Enum مباشرة دون الاعتماد على جدول خارجي
    attendance_type = db.Column(
        db.Enum(AttendanceTypeEnum, name='attendance_type_enum'),
        nullable=False
    )

    is_excused_absence = db.Column(db.Boolean, default=False)
    excuse_document = db.Column(db.String(255), nullable=True)

    check_in = db.Column(db.Time, nullable=True)
    check_out = db.Column(db.Time, nullable=True)

    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    employee = db.relationship('Employee', backref='monthly_attendance', lazy=True)

    __table_args__ = (
        db.UniqueConstraint('employee_id', 'date', name='unique_employee_date'),
    )

    def __repr__(self):
        return f"<MonthlyAttendance: Employee {self.employee_id}, Date {self.date}, Type {self.attendance_type}>"
