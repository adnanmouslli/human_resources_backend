from app import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# جداول الربط للعلاقات المتعددة
class UserDepartmentHead(db.Model):
    """
    جدول ربط المستخدمين بالأقسام التي يرأسونها
    """
    __tablename__ = 'user_department_heads'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='CASCADE'), primary_key=True)
    role_type = db.Column(db.String(20), nullable=False)  # 'head' أو 'deputy'
    created_at = db.Column(db.DateTime, default=datetime.now)
    notes = db.Column(db.Text, nullable=True)

class UserBranchHead(db.Model):
    """
    جدول ربط المستخدمين بالفروع التي يرأسونها
    """
    __tablename__ = 'user_branch_heads'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id', ondelete='CASCADE'), primary_key=True)
    role_type = db.Column(db.String(20), nullable=False)  # 'head' أو 'deputy'
    created_at = db.Column(db.DateTime, default=datetime.now)
    notes = db.Column(db.Text, nullable=True)

class User(db.Model):
    """
    نموذج المستخدم: يمثل المستخدمين المسجلين في النظام مع إدارة الصلاحيات
    """
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)  # اسم المستخدم
    password = db.Column(db.String(255), nullable=False)  # كلمة المرور (مشفرة)
    is_active = db.Column(db.Boolean, default=True)  # حالة الحساب
    
    # أنواع المستخدمين: super_admin, branch_head, department_head, branch_deputy, department_deputy, employee
    user_type = db.Column(db.String(50), nullable=False)
    
    # ربط المستخدم بالموظف (null في حالة super_admin)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    
    # الحقول القديمة - نبقيها للتوافق مع الإصدارات السابقة (يمكن حذفها لاحقاً)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    
    # تواريخ النظام
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # العلاقات الجديدة للرئاسة المتعددة
    managed_departments = db.relationship(
        'Department',
        secondary='user_department_heads',
        back_populates='managers',
        lazy='dynamic'
    )
    
    managed_branches = db.relationship(
        'Branch',
        secondary='user_branch_heads',
        back_populates='managers',
        lazy='dynamic'
    )

    def __repr__(self):
        return f"<User {self.username} ({self.user_type})>"
    
    def set_password(self, password):
        """تشفير كلمة المرور"""
        self.password = generate_password_hash(password)
        
    def check_password(self, password):
        """التحقق من صحة كلمة المرور"""
        return check_password_hash(self.password, password)
    
    # دوال التحقق من نوع المستخدم
    def is_super_admin(self):
        """التحقق مما إذا كان المستخدم مدير النظام"""
        return self.user_type == 'super_admin'
    
    def is_branch_head(self):
        """التحقق مما إذا كان المستخدم رئيس فرع"""
        return self.user_type == 'branch_head'
    
    def is_department_head(self):
        """التحقق مما إذا كان المستخدم رئيس قسم"""
        return self.user_type == 'department_head'
    
    def is_branch_deputy(self):
        """التحقق مما إذا كان المستخدم نائب رئيس فرع"""
        return self.user_type == 'branch_deputy'
    
    def is_department_deputy(self):
        """التحقق مما إذا كان المستخدم نائب رئيس قسم"""
        return self.user_type == 'department_deputy'
    
    def is_employee(self):
        """التحقق مما إذا كان المستخدم موظف عادي"""
        return self.user_type == 'employee'

    # دوال إدارة الأقسام والفروع المتعددة
    def add_department_management(self, department_id, role_type='head'):
        """إضافة قسم لإدارة المستخدم"""
        existing = UserDepartmentHead.query.filter_by(
            user_id=self.id, 
            department_id=department_id
        ).first()
        
        if not existing:
            management = UserDepartmentHead(
                user_id=self.id,
                department_id=department_id,
                role_type=role_type
            )
            db.session.add(management)
            return True
        return False

    def remove_department_management(self, department_id):
        """إزالة قسم من إدارة المستخدم"""
        management = UserDepartmentHead.query.filter_by(
            user_id=self.id, 
            department_id=department_id
        ).first()
        
        if management:
            db.session.delete(management)
            return True
        return False

    def add_branch_management(self, branch_id, role_type='head'):
        """إضافة فرع لإدارة المستخدم"""
        existing = UserBranchHead.query.filter_by(
            user_id=self.id, 
            branch_id=branch_id
        ).first()
        
        if not existing:
            management = UserBranchHead(
                user_id=self.id,
                branch_id=branch_id,
                role_type=role_type
            )
            db.session.add(management)
            return True
        return False

    def remove_branch_management(self, branch_id):
        """إزالة فرع من إدارة المستخدم"""
        management = UserBranchHead.query.filter_by(
            user_id=self.id, 
            branch_id=branch_id
        ).first()
        
        if management:
            db.session.delete(management)
            return True
        return False

    def get_managed_department_ids(self):
        """الحصول على معرفات الأقسام التي يديرها المستخدم"""
        managements = UserDepartmentHead.query.filter_by(user_id=self.id).all()
        return [m.department_id for m in managements]

    def get_managed_branch_ids(self):
        """الحصول على معرفات الفروع التي يديرها المستخدم"""
        managements = UserBranchHead.query.filter_by(user_id=self.id).all()
        return [m.branch_id for m in managements]

    def get_accessible_employees(self):
        """الحصول على قائمة الموظفين الذين يمكن للمستخدم الوصول إليهم"""
        from app.models.employee import Employee
        
        if self.is_super_admin():
            # super admin يمكنه الوصول إلى جميع الموظفين
            return Employee.query.all()
        
        elif self.is_branch_head() or self.is_branch_deputy():
            # رئيس الفرع أو نائبه يمكنه الوصول إلى موظفي جميع الفروع التي يديرها
            managed_branch_ids = self.get_managed_branch_ids()
            
            # إضافة الفرع القديم للتوافق مع النظام السابق
            if self.branch_id and self.branch_id not in managed_branch_ids:
                managed_branch_ids.append(self.branch_id)
            
            if managed_branch_ids:
                return Employee.query.filter(Employee.branch_id.in_(managed_branch_ids)).all()
        
        elif self.is_department_head() or self.is_department_deputy():
            # رئيس القسم أو نائبه يمكنه الوصول إلى موظفي جميع الأقسام التي يديرها
            managed_department_ids = self.get_managed_department_ids()
            
            # إضافة القسم القديم للتوافق مع النظام السابق
            if self.department_id and self.department_id not in managed_department_ids:
                managed_department_ids.append(self.department_id)
            
            if managed_department_ids:
                return Employee.query.filter(Employee.department_id.in_(managed_department_ids)).all()
        
        elif self.employee_id:
            # الموظف العادي يمكنه فقط الوصول إلى بياناته
            return [Employee.query.get(self.employee_id)]
        
        return []

    def get_accessible_holidays(self):
        """الحصول على قائمة العطل التي يمكن للمستخدم الوصول إليها"""
        from app.models.holiday import Holiday
        
        if self.is_super_admin():
            # super admin يمكنه الوصول إلى جميع العطل
            return Holiday.query.filter_by(is_active=True).all()
        
        elif self.is_branch_head() or self.is_branch_deputy():
            # رئيس الفرع أو نائبه يمكنه الوصول إلى عطل جميع الفروع التي يديرها والعطل العامة
            managed_branch_ids = self.get_managed_branch_ids()
            
            # إضافة الفرع القديم للتوافق
            if self.branch_id and self.branch_id not in managed_branch_ids:
                managed_branch_ids.append(self.branch_id)
            
            if managed_branch_ids:
                return Holiday.query.filter(
                    Holiday.is_active == True,
                    db.or_(
                        Holiday.branch_id.in_(managed_branch_ids),
                        Holiday.branch_id.is_(None)
                    )
                ).all()
        
        elif self.is_department_head() or self.is_department_deputy():
            # رئيس القسم أو نائبه يمكنه الوصول إلى عطل جميع الأقسام التي يديرها والعطل العامة
            managed_department_ids = self.get_managed_department_ids()
            
            # إضافة القسم القديم للتوافق
            if self.department_id and self.department_id not in managed_department_ids:
                managed_department_ids.append(self.department_id)
            
            if managed_department_ids:
                return Holiday.query.filter(
                    Holiday.is_active == True,
                    db.or_(
                        Holiday.department_id.in_(managed_department_ids),
                        Holiday.department_id.is_(None)
                    )
                ).all()
        
        # الموظف العادي - العطل العامة فقط
        return Holiday.query.filter(
            Holiday.is_active == True,
            Holiday.branch_id.is_(None),
            Holiday.department_id.is_(None)
        ).all()

    def can_manage_holiday(self, holiday):
        """التحقق من إمكانية إدارة عطلة معينة"""
        if self.is_super_admin():
            return True
        
        # رئيس الفرع يمكنه إدارة عطل فروعه والعطل العامة
        if self.is_branch_head():
            managed_branch_ids = self.get_managed_branch_ids()
            if self.branch_id and self.branch_id not in managed_branch_ids:
                managed_branch_ids.append(self.branch_id)
            
            return (holiday.branch_id in managed_branch_ids) or holiday.branch_id is None
        
        # رئيس القسم يمكنه إدارة عطل أقسامه والعطل العامة
        if self.is_department_head():
            managed_department_ids = self.get_managed_department_ids()
            if self.department_id and self.department_id not in managed_department_ids:
                managed_department_ids.append(self.department_id)
            
            return (holiday.department_id in managed_department_ids) or holiday.department_id is None
        
        return False

    def can_create_transaction_for_employee(self, employee_id, transaction_type=None):
        """
        التحقق من إمكانية إنشاء معاملة لموظف معين
        """
        from app.models.employee import Employee
        
        employee = Employee.query.get(employee_id)
        if not employee:
            return False
        
        # السوبر أدمن يمكنه إنشاء معاملات لأي موظف
        if self.is_super_admin():
            return True
        
        # رئيس الفرع أو نائبه
        if self.is_branch_head() or self.is_branch_deputy():
            managed_branch_ids = self.get_managed_branch_ids()
            if self.branch_id and self.branch_id not in managed_branch_ids:
                managed_branch_ids.append(self.branch_id)
            
            if employee.branch_id in managed_branch_ids:
                return True
        
        # رئيس القسم أو نائبه
        if self.is_department_head() or self.is_department_deputy():
            managed_department_ids = self.get_managed_department_ids()
            if self.department_id and self.department_id not in managed_department_ids:
                managed_department_ids.append(self.department_id)
            
            if employee.department_id in managed_department_ids:
                return True
        
        # الموظف نفسه (في حالات معينة مثل الإجازات)
        if self.employee_id == employee.id and transaction_type in ['hourly_leave', 'daily_leave']:
            return True
        
        return False

    def get_department_transaction_summary(self, start_date=None, end_date=None):
        """
        ملخص معاملات الأقسام/الفروع التي يديرها المستخدم
        """
        from app.models.transaction import Transaction
        from datetime import datetime, timedelta
        
        if not start_date:
            start_date = datetime.now().replace(day=1)  # بداية الشهر الحالي
        
        if not end_date:
            end_date = datetime.now()
        
        query = Transaction.query.filter(
            Transaction.created_at >= start_date,
            Transaction.created_at <= end_date
        )
        
        # فلترة حسب صلاحيات المستخدم
        if self.is_super_admin():
            pass  # لا حاجة لفلترة
        elif self.is_branch_head() or self.is_branch_deputy():
            # معاملات موظفي جميع الفروع التي يديرها
            managed_branch_ids = self.get_managed_branch_ids()
            if self.branch_id and self.branch_id not in managed_branch_ids:
                managed_branch_ids.append(self.branch_id)
            
            if managed_branch_ids:
                from app.models.employee import Employee
                branch_employee_ids = [emp.id for emp in Employee.query.filter(Employee.branch_id.in_(managed_branch_ids)).all()]
                query = query.filter(Transaction.employee_id.in_(branch_employee_ids))
            else:
                return None
                
        elif self.is_department_head() or self.is_department_deputy():
            # معاملات موظفي جميع الأقسام التي يديرها
            managed_department_ids = self.get_managed_department_ids()
            if self.department_id and self.department_id not in managed_department_ids:
                managed_department_ids.append(self.department_id)
            
            if managed_department_ids:
                from app.models.employee import Employee
                dept_employee_ids = [emp.id for emp in Employee.query.filter(Employee.department_id.in_(managed_department_ids)).all()]
                query = query.filter(Transaction.employee_id.in_(dept_employee_ids))
            else:
                return None
        else:
            # موظف عادي - فقط معاملاته
            if self.employee_id:
                query = query.filter(Transaction.employee_id == self.employee_id)
            else:
                return None
        
        transactions = query.all()
        
        # إنشاء الملخص...
        summary = {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'managed_departments': self.get_managed_department_ids(),
            'managed_branches': self.get_managed_branch_ids(),
            'total': len(transactions),
            'by_status': {
                'pending': len([t for t in transactions if t.status == 'pending']),
                'approved': len([t for t in transactions if t.status == 'approved']),
                'rejected': len([t for t in transactions if t.status == 'rejected'])
            },
            'by_type': {}
        }
        
        # تصنيف حسب النوع
        transaction_types = ['advance', 'reward', 'penalty', 'hourly_leave', 'daily_leave']
        for trans_type in transaction_types:
            type_transactions = [t for t in transactions if t.transaction_type == trans_type]
            summary['by_type'][trans_type] = {
                'total': len(type_transactions),
                'pending': len([t for t in type_transactions if t.status == 'pending']),
                'approved': len([t for t in type_transactions if t.status == 'approved']),
                'rejected': len([t for t in type_transactions if t.status == 'rejected'])
            }
        
        return summary

    def has_permission(self, action, resource=None):
        """
        التحقق من صلاحيات المستخدم
        action: العملية (view, create, update, delete)
        resource: المورد (employees, departments, branches, etc.)
        """
        # Super admin لديه كل الصلاحيات
        if self.is_super_admin():
            return True
        
        # صلاحيات رئيس الفرع
        if self.is_branch_head():
            if resource == 'employees' and action in ['view', 'create', 'update']:
                return True
            if resource == 'departments' and action in ['view']:
                return True
            if resource == 'branches' and action in ['view', 'update']:
                # يمكنه إدارة أي فرع يديره
                return len(self.get_managed_branch_ids()) > 0 or self.branch_id is not None
        
        # صلاحيات رئيس القسم
        if self.is_department_head():
            if resource == 'employees' and action in ['view', 'create', 'update']:
                return True
            if resource == 'departments' and action in ['view', 'update']:
                # يمكنه إدارة أي قسم يديره
                return len(self.get_managed_department_ids()) > 0 or self.department_id is not None
        
        # صلاحيات نائب رئيس الفرع
        if self.is_branch_deputy():
            if resource == 'employees' and action in ['view', 'create']:
                return True
            if resource in ['departments', 'branches'] and action == 'view':
                return True
        
        # صلاحيات نائب رئيس القسم
        if self.is_department_deputy():
            if resource == 'employees' and action in ['view', 'create']:
                return True
            if resource == 'departments' and action == 'view':
                return True
        
        # المستخدم العادي (موظف)
        if self.is_employee():
            if resource == 'employees' and action == 'view':
                return self.is_view_own_data_only()
            if resource in ['departments', 'branches'] and action == 'view':
                return True
        
        return False

    def is_view_own_data_only(self):
        """التحقق مما إذا كان المستخدم يمكنه فقط عرض بياناته الخاصة"""
        return self.is_employee()





########################################3

    def get_accessible_transactions(self):
        """
        الحصول على المعاملات التي يمكن للمستخدم الوصول إليها
        """
        from app.models.transaction import Transaction
        
        if self.is_super_admin():
            # السوبر أدمن يمكنه الوصول إلى جميع المعاملات
            return Transaction.query.all()
        
        # الحصول على الموظفين الذين يمكن الوصول إليهم
        accessible_employee_ids = [emp.id for emp in self.get_accessible_employees()]
        
        if accessible_employee_ids:
            # المعاملات للموظفين التابعين + المعاملات التي طلبها المستخدم
            return Transaction.query.filter(
                db.or_(
                    Transaction.employee_id.in_(accessible_employee_ids),
                    Transaction.requested_by == self.id
                )
            ).all()
        else:
            # فقط المعاملات التي طلبها المستخدم
            return Transaction.query.filter_by(requested_by=self.id).all()

    def get_pending_approvals_count(self):
        """
        الحصول على عدد المعاملات المعلقة التي تحتاج موافقة هذا المستخدم
        """
        from app.models.transaction import TransactionApproval, Transaction
        
        return TransactionApproval.query.filter_by(
            approver_id=self.id,
            status='pending'
        ).join(Transaction).filter(
            Transaction.status == 'pending'
        ).count()

    def get_my_transaction_statistics(self):
        """
        إحصائيات المعاملات الخاصة بالمستخدم
        """
        from app.models.transaction import Transaction, TransactionApproval
        
        # المعاملات التي طلبها المستخدم
        my_transactions = Transaction.query.filter_by(requested_by=self.id)
        
        # المعاملات التي يحتاج للموافقة عليها
        pending_approvals = TransactionApproval.query.filter_by(
            approver_id=self.id,
            status='pending'
        ).join(Transaction).filter(Transaction.status == 'pending')
        
        # المعاملات التي وافق عليها
        approved_by_me = TransactionApproval.query.filter_by(
            approver_id=self.id,
            status='approved'
        )
        
        return {
            'requested_by_me': {
                'total': my_transactions.count(),
                'pending': my_transactions.filter_by(status='pending').count(),
                'approved': my_transactions.filter_by(status='approved').count(),
                'rejected': my_transactions.filter_by(status='rejected').count()
            },
            'pending_my_approval': pending_approvals.count(),
            'approved_by_me': approved_by_me.count()
        }

    def can_manage_transaction(self, transaction):
        """
        التحقق من إمكانية إدارة معاملة معينة (تحديث، حذف)
        """
        # السوبر أدمن يمكنه إدارة أي معاملة
        if self.is_super_admin():
            return True
        
        # منشئ المعاملة يمكنه إدارتها
        if transaction.requested_by == self.id:
            return True
        
        return False

    def has_transaction_approval_permission(self, transaction):
        """
        التحقق من وجود صلاحية الموافقة على معاملة معينة
        """
        return transaction.can_be_approved_by(self)

    # ================================ دوال مساعدة إضافية ================================

    def get_department_transaction_summary(self, start_date=None, end_date=None):
        """
        ملخص معاملات القسم/الفرع (للرؤساء والنواب)
        """
        from app.models.transaction import Transaction
        from datetime import datetime, timedelta
        
        if not start_date:
            start_date = datetime.now().replace(day=1)  # بداية الشهر الحالي
        
        if not end_date:
            end_date = datetime.now()
        
        query = Transaction.query.filter(
            Transaction.created_at >= start_date,
            Transaction.created_at <= end_date
        )
        
        # فلترة حسب صلاحيات المستخدم
        if self.is_super_admin():
            pass  # لا حاجة لفلترة
        elif self.is_branch_head() or self.is_branch_deputy():
            # معاملات موظفي الفرع
            if self.branch_id:
                from app.models.employee import Employee
                branch_employee_ids = [emp.id for emp in Employee.query.filter_by(branch_id=self.branch_id).all()]
                query = query.filter(Transaction.employee_id.in_(branch_employee_ids))
            else:
                return None
        elif self.is_department_head() or self.is_department_deputy():
            # معاملات موظفي القسم
            if self.department_id:
                from app.models.employee import Employee
                dept_employee_ids = [emp.id for emp in Employee.query.filter_by(department_id=self.department_id).all()]
                query = query.filter(Transaction.employee_id.in_(dept_employee_ids))
            else:
                return None
        else:
            # موظف عادي - فقط معاملاته
            if self.employee_id:
                query = query.filter(Transaction.employee_id == self.employee_id)
            else:
                return None
        
        transactions = query.all()
        
        summary = {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'total': len(transactions),
            'by_status': {
                'pending': len([t for t in transactions if t.status == 'pending']),
                'approved': len([t for t in transactions if t.status == 'approved']),
                'rejected': len([t for t in transactions if t.status == 'rejected'])
            },
            'by_type': {}
        }
        
        # تصنيف حسب النوع
        transaction_types = ['advance', 'reward', 'penalty', 'hourly_leave', 'daily_leave']
        for trans_type in transaction_types:
            type_transactions = [t for t in transactions if t.transaction_type == trans_type]
            summary['by_type'][trans_type] = {
                'total': len(type_transactions),
                'pending': len([t for t in type_transactions if t.status == 'pending']),
                'approved': len([t for t in type_transactions if t.status == 'approved']),
                'rejected': len([t for t in type_transactions if t.status == 'rejected'])
            }
        
        return summary