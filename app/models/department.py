from app import db
from datetime import datetime

class Department(db.Model):
    """
    نموذج القسم: يمثل الأقسام الإدارية في المؤسسة
    """
    __tablename__ = 'departments'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)  # اسم القسم
    description = db.Column(db.Text, nullable=True)  # وصف القسم
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # العلاقة مع الفروع (علاقة متعددة-متعددة)
    branches = db.relationship(
        'Branch', 
        secondary='branch_departments', 
        back_populates='departments', 
        lazy='dynamic'
    )

    # علاقة مع الموظفين (الموظفين في هذا القسم)
    employees = db.relationship(
        'Employee', 
        backref=db.backref('department', lazy=True),
        lazy='dynamic'
    )

    # العلاقة مع المستخدمين (مثل رئيس القسم أو نائبه)
    users = db.relationship(
        'User', 
        foreign_keys='User.department_id', 
        backref=db.backref('department', lazy=True), 
        lazy='dynamic'
    )
    
    def __repr__(self):
        return f"<Department {self.name}>"
    
    def get_department_head(self):
        """الحصول على رئيس القسم"""
        return self.users.filter_by(user_type='department_head').first()
    
    def get_department_deputy(self):
        """الحصول على نائب رئيس القسم"""
        return self.users.filter_by(user_type='department_deputy').first()
    
    def get_employee_count(self):
        """الحصول على عدد الموظفين في القسم"""
        return self.employees.count()


# جدول العلاقة بين الفروع والأقسام
class BranchDepartment(db.Model):
    """
    جدول العلاقة بين الفروع والأقسام (جدول ربط)
    """
    __tablename__ = 'branch_departments'
    
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id', ondelete='CASCADE'), primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='CASCADE'), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    notes = db.Column(db.Text, nullable=True)  # ملاحظات