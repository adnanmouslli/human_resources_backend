from app import db
from datetime import datetime

from app.models.user import User

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

    # العلاقة الجديدة مع المديرين
    managers = db.relationship(
        'User',
        secondary='user_branch_heads',
        back_populates='managed_branches',
        lazy='dynamic'
    )
    
    def __repr__(self):
        return f"<Branch {self.name}>"
    

     
    def get_branch_heads(self):
        """الحصول على رؤساء الفرع"""
        from app.models.user import UserBranchHead
        heads = db.session.query(User).join(UserBranchHead).filter(
            UserBranchHead.branch_id == self.id,
            UserBranchHead.role_type == 'head'
        ).all()
        return heads
    
    def get_branch_deputies(self):
        """الحصول على نواب رؤساء الفرع"""
        from app.models.user import UserBranchHead
        deputies = db.session.query(User).join(UserBranchHead).filter(
            UserBranchHead.branch_id == self.id,
            UserBranchHead.role_type == 'deputy'
        ).all()
        return deputies
    
    def get_all_managers(self):
        """الحصول على جميع مديري الفرع (رؤساء ونواب)"""
        return self.managers.all()
    
    def add_manager(self, user, role_type='head'):
        """إضافة مدير للفرع"""
        return user.add_branch_management(self.id, role_type)
    
    def remove_manager(self, user):
        """إزالة مدير من الفرع"""
        return user.remove_branch_management(self.id)
    
    def get_department_count(self):
        """الحصول على عدد الأقسام في الفرع"""
        return self.departments.count()
    
    def get_employee_count(self):
        """الحصول على عدد الموظفين في الفرع"""
        return self.employees.count()
    
    def can_be_managed_by(self, user):
        """التحقق من إمكانية إدارة الفرع بواسطة مستخدم معين"""
        if user.is_super_admin():
            return True
        
        # التحقق من كون المستخدم مدير لهذا الفرع
        managed_branch_ids = user.get_managed_branch_ids()
        return self.id in managed_branch_ids or user.branch_id == self.id
    
    def get_branch_head(self):
        """الحصول على رئيس الفرع"""
        return self.users.filter_by(user_type='branch_head').first()
    
    def get_branch_deputy(self):
        """الحصول على نائب رئيس الفرع"""
        return self.users.filter_by(user_type='branch_deputy').first()
