from app import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)  # اسم المستخدم
    password = db.Column(db.String(255), nullable=False)  # كلمة المرور
    is_active = db.Column(db.Boolean, default=True)  # حالة المستخدم (نشط أو غير نشط)
    
    # حقل يحدد نوع المستخدم (super_admin, branch_head, department_head, branch_deputy, department_deputy, employee)
    user_type = db.Column(db.String(50), nullable=True)
    
    # ربط المستخدم بالموظف (null في حالة super_admin)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    employee = db.relationship('Employee', backref=db.backref('user_account', uselist=False), lazy=True)
    
    # ربط المستخدم بالقسم (null في حالة super_admin أو رؤساء الفروع)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    department = db.relationship('Department', backref=db.backref('department_users', lazy=True), lazy=True)
    
    # ربط المستخدم بالفرع (null في حالة super_admin أو رؤساء الأقسام)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    branch = db.relationship('Branch', backref=db.backref('branch_users', lazy=True), lazy=True)
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def set_password(self, password):
        self.password = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password, password)
    
    def is_super_admin(self):
        return self.user_type == 'super_admin'
    
    def is_branch_head(self):
        return self.user_type == 'branch_head'
    
    def is_department_head(self):
        return self.user_type == 'department_head'
    
    def is_branch_deputy(self):
        return self.user_type == 'branch_deputy'
    
    def is_department_deputy(self):
        return self.user_type == 'department_deputy'
    
    def has_permission(self, action, resource=None):
        """
        التحقق من صلاحيات المستخدم بطريقة مبسطة
        action: العملية (view, create, update, delete)
        resource: المورد (employees, departments, branches)
        """
        # Super admin لديه كل الصلاحيات
        if self.is_super_admin():
            return True
        
        # صلاحيات رئيس الفرع
        if self.is_branch_head():
            # يمكنه إدارة الموظفين والأقسام في فرعه
            if resource == 'employees' and action in ['view', 'create', 'update']:
                return True
            if resource == 'departments' and action in ['view']:
                return True
            if resource == 'branches' and action in ['view', 'update'] and self.branch_id:
                return True
        
        # صلاحيات رئيس القسم
        if self.is_department_head():
            # يمكنه إدارة الموظفين في قسمه
            if resource == 'employees' and action in ['view', 'create', 'update']:
                return True
            if resource == 'departments' and action in ['view', 'update'] and self.department_id:
                return True
        
        # صلاحيات نائب رئيس الفرع
        if self.is_branch_deputy():
            # يمكنه عرض وإنشاء موظفين في فرعه
            if resource == 'employees' and action in ['view', 'create']:
                return True
            if resource == 'departments' and action == 'view':
                return True
            if resource == 'branches' and action == 'view':
                return True
        
        # صلاحيات نائب رئيس القسم
        if self.is_department_deputy():
            # يمكنه عرض وإنشاء موظفين في قسمه
            if resource == 'employees' and action in ['view', 'create']:
                return True
            if resource == 'departments' and action == 'view':
                return True
        
        # المستخدم العادي (موظف)
        if self.user_type == 'employee':
            # يمكنه فقط عرض البيانات الخاصة به
            if resource == 'employees' and action == 'view':
                return self.is_view_own_data_only()
            if resource in ['departments', 'branches'] and action == 'view':
                return True
        
        return False
    
    def is_view_own_data_only(self):
        """
        التحقق مما إذا كان المستخدم يمكنه فقط عرض بياناته الخاصة
        """
        return self.user_type == 'employee'
    
    def get_accessible_employees(self):
        """
        الحصول على قائمة الموظفين الذين يمكن للمستخدم الوصول إليهم
        """
        from app.models.employee import Employee
        
        if self.is_super_admin():
            # super admin يمكنه الوصول إلى جميع الموظفين
            return Employee.query.all()
        
        elif self.is_branch_head() or self.is_branch_deputy():
            # رئيس الفرع أو نائبه يمكنه الوصول إلى موظفي الفرع
            if self.branch_id:
                return Employee.query.filter_by(branch_id=self.branch_id).all()
        
        elif self.is_department_head() or self.is_department_deputy():
            # رئيس القسم أو نائبه يمكنه الوصول إلى موظفي القسم
            if self.department_id:
                return Employee.query.filter_by(department_id=self.department_id).all()
        
        elif self.employee_id:
            # الموظف العادي يمكنه فقط الوصول إلى بياناته
            return [Employee.query.get(self.employee_id)]
        
        return []

    def __repr__(self):
        return f"<User {self.username} ({self.user_type})>"