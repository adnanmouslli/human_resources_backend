# monthly_attendance.py

from app import db
from datetime import date

class MonthlyAttendance(db.Model):
    __tablename__ = 'monthly_attendance'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    month = db.Column(db.Integer, nullable=False)  # مثال: 4
    year = db.Column(db.Integer, nullable=False)   # مثال: 2025

    total_working_days = db.Column(db.Integer, nullable=False, default=0)
    present_days = db.Column(db.Integer, nullable=False, default=0)
    absent_days = db.Column(db.Integer, nullable=False, default=0)
    late_days = db.Column(db.Integer, nullable=False, default=0)
    vacation_days = db.Column(db.Integer, nullable=False, default=0)
    sick_days = db.Column(db.Integer, nullable=False, default=0)
    excused_days = db.Column(db.Integer, nullable=False, default=0)
    holiday_days = db.Column(db.Integer, nullable=False, default=0)

    salary_deduction = db.Column(db.Numeric(10, 2), nullable=True, default=0)
    bonus = db.Column(db.Numeric(10, 2), nullable=True, default=0)
    notes = db.Column(db.Text, nullable=True)


    def __repr__(self):
        return f"<MonthlyAttendance Employee {self.employee_id} - {self.month}/{self.year}>"

"""
شرح الجدول:
هذا الجدول يقوم بتجميع بيانات الحضور والانصراف للموظف خلال شهر كامل.
يتم استخدامه لإصدار تقارير شهرية أو احتساب الراتب، حيث يحتوي على عدد أيام الحضور، الغياب، التأخير، الإجازات... إلخ.
يرتبط بالموظف من خلال `employee_id`.
"""
