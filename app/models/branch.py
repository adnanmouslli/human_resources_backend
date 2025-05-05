from app import db
from datetime import datetime

# Branch Model (الفروع)
class Branch(db.Model):
    __tablename__ = 'branches'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)  # اسم الفرع
    address = db.Column(db.String(255), nullable=True)  # عنوان الفرع
    phone = db.Column(db.String(20), nullable=True)  # رقم هاتف الفرع
    email = db.Column(db.String(100), nullable=True)  # البريد الإلكتروني للفرع
    notes = db.Column(db.Text, nullable=True)  # ملاحظات
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # العلاقة مع الأقسام (من خلال جدول العلاقات)
    departments = db.relationship('Department', secondary='branch_departments', back_populates='branches')
    
    # العلاقة مع الموظفين
    employees = db.relationship('Employee', backref='branch', lazy=True)
    
    def __repr__(self):
        return f"<Branch {self.name}>"
