from app import db
from datetime import datetime

from app.models.user import User

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
    

    # العلاقة الجديدة مع المديرين
    managers = db.relationship(
        'User',
        secondary='user_department_heads',
        back_populates='managed_departments',
        lazy='dynamic'
    )

    def __repr__(self):
        return f"<Department {self.name}>"
    
    def get_department_heads(self):
        """جميع رؤساء القسم من جدول الربط (مع توافق الحقل القديم)"""
        from app.models.user import UserDepartmentHead
        heads = db.session.query(User).join(UserDepartmentHead).filter(
            UserDepartmentHead.department_id == self.id,
            UserDepartmentHead.role_type == 'head',
            User.is_active == True,
        ).all()
        if heads:
            return heads
        legacy = self.users.filter_by(user_type='department_head', is_active=True).all()
        return list(legacy)

    def get_department_head(self):
        """رئيس القسم (أول رئيس من جدول الربط، مع توافق قديم)"""
        heads = self.get_department_heads()
        return heads[0] if heads else None
    
    def get_department_deputy(self):
        """نائب رئيس القسم (أول نائب)"""
        deputies = self.get_department_deputies()
        return deputies[0] if deputies else None

    def get_department_deputies(self):
        """الحصول على نواب رؤساء القسم"""
        from app.models.user import UserDepartmentHead
        deputies = db.session.query(User).join(UserDepartmentHead).filter(
            UserDepartmentHead.department_id == self.id,
            UserDepartmentHead.role_type == 'deputy',
            User.is_active == True,
        ).all()
        if deputies:
            return deputies
        return list(self.users.filter_by(user_type='department_deputy', is_active=True).all())

    def get_employee_count(self):
        """الحصول على عدد الموظفين في القسم"""
        return self.employees.count()
    
    def get_all_managers(self):
        """الحصول على جميع مديري القسم (رؤساء ونواب)"""
        return self.managers.all()
    
    def add_manager(self, user, role_type='head'):
        """إضافة مدير للقسم"""
        return user.add_department_management(self.id, role_type)
    
    def remove_manager(self, user):
        """إزالة مدير من القسم"""
        return user.remove_department_management(self.id)
    
    def can_be_managed_by(self, user):
        """التحقق من إمكانية إدارة القسم بواسطة مستخدم معين"""
        if user.is_super_admin():
            return True
        
        return user.manages_department(self.id)


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