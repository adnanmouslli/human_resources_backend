# app/models/attendance.py
from app import db
from datetime import date

class Attendance(db.Model):
    __tablename__ = 'attendances'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empId = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    createdAt = db.Column(db.Date, default=date.today)        # تاريخ فقط
    checkInTime = db.Column(db.Time, nullable=True)
    checkOutTime = db.Column(db.Time, nullable=True)

    # اختياري
    checkInReason = db.Column(db.String(255), nullable=True)
    checkOutReason = db.Column(db.String(255), nullable=True)
    productionQuantity = db.Column(db.Float, nullable=True)

    # ✅ الجديد
    status = db.Column(db.String(20), nullable=True, default="approved")  # pending / approved / rejected

    def __repr__(self):
        return f"<Attendance {self.id}, Employee {self.empId}>"
