# app/models/attendance.py

from app import db
from datetime import date, time
from app.models.attendance_type import AttendanceType  # استيراد الـ Enum من ملف attendance_type

class Attendance(db.Model):
    __tablename__ = 'attendances'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # ID تلقائي
    empId = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)  # ForeignKey من جدول Employee
    createdAt = db.Column(db.Date, default=date.today)  # تاريخ التسجيل فقط
    checkInTime = db.Column(db.Time, nullable=True)  # وقت الحضور فقط
    checkOutTime = db.Column(db.Time, nullable=True)  # وقت الانصراف فقط
    
    # الأعمدة الجديدة
    checkInReason = db.Column(db.String(255), nullable=True)  # سبب الدخول (اختياري)
    checkOutReason = db.Column(db.String(255), nullable=True)  # سبب الخروج (اختياري)
    productionQuantity = db.Column(db.Float, nullable=True)  # كمية الإنتاج (اختياري)
    
    # إضافة ForeignKey إلى AttendanceType
    attendance_type_id = db.Column(db.Integer, db.ForeignKey('attendance_types.id'), nullable=False)
    attendance_type = db.relationship('AttendanceType', backref='attendances', lazy=True)

    def __repr__(self):
        return f"<Attendance {self.id}, Employee {self.empId}>"
