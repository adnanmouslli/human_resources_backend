from app import db
from datetime import datetime

class Branch(db.Model):
    """
    نموذج الفرع: يمثل الفروع الفعلية للمؤسسة في مختلف المواقع
    """
    __tablename__ = 'branches'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)  # اسم الفرع
    address = db.Column(db.String(255), nullable=True)  # عنوان الفرع
    phone = db.Column(db.String(20), nullable=True)  # رقم هاتف الفرع
    email = db.Column(db.String(100), nullable=True)  # البريد الإلكتروني للفرع
    notes = db.Column(db.Text, nullable=True)  # ملاحظات
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # العلاقة مع الأقسام (علاقة متعددة-متعددة)
    departments = db.relationship(
        'Department', 
        secondary='branch_departments', 
        back_populates='branches',
        lazy='dynamic'
    )
    
    # العلاقة مع الموظفين (الموظفين في هذا الفرع)
    employees = db.relationship(
        'Employee', 
        backref='branch', 
        lazy='dynamic'
    )
    
    # العلاقة مع المستخدمين (مثل رئيس الفرع أو نائبه)
    users = db.relationship(
        'User',
        foreign_keys='User.branch_id',
        backref=db.backref('branch', lazy=True),
        lazy='dynamic'
    )
    
    def __repr__(self):
        return f"<Branch {self.name}>"
    
    def get_branch_head(self):
        """الحصول على رئيس الفرع"""
        return self.users.filter_by(user_type='branch_head').first()
    
    def get_branch_deputy(self):
        """الحصول على نائب رئيس الفرع"""
        return self.users.filter_by(user_type='branch_deputy').first()
    
    def get_department_count(self):
        """الحصول على عدد الأقسام في الفرع"""
        return self.departments.count()
    
    def get_employee_count(self):
        """الحصول على عدد الموظفين في الفرع"""
        return self.employees.count()