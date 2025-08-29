# app/models/attendance.py

from app import db
from datetime import date

class Attendance(db.Model):
    __tablename__ = 'attendances'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # ID تلقائي
    empId = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)  # ForeignKey من جدول Employee
    createdAt = db.Column(db.Date, default=date.today)  # تاريخ التسجيل فقط
    checkInTime = db.Column(db.Time, nullable=True)  # وقت الحضور فقط
    checkOutTime = db.Column(db.Time, nullable=True)  # وقت الانصراف فقط

    # الأعمدة الاختيارية
    checkInReason = db.Column(db.String(255), nullable=True)  # سبب الدخول
    checkOutReason = db.Column(db.String(255), nullable=True)  # سبب الخروج
    productionQuantity = db.Column(db.Float, nullable=True)  # كمية الإنتاج

    def __repr__(self):
        return f"<Attendance {self.id}, Employee {self.empId}>"
