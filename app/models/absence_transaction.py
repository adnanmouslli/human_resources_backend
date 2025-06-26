from app import db
from datetime import datetime
from sqlalchemy import CheckConstraint

from app.models.absence_answer import AbsenceAnswer

class AbsenceTransaction(db.Model):
    """
    معاملات الغياب
    """
    __tablename__ = 'absence_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # معلومات المعاملة الأساسية
    transaction_number = db.Column(db.String(50), nullable=True, unique=True)  # رقم المعاملة
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    absence_date = db.Column(db.Date, nullable=False)  # تاريخ الغياب
    shift_id = db.Column(db.Integer, db.ForeignKey('shift.id'), nullable=True)  # الوردية المرتبطة
    
    # حالة المعاملة
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, approved, rejected
    
    # تفاصيل إضافية
    absence_reason = db.Column(db.Text, nullable=True)  # سبب الغياب (إذا تم الإبلاغ)
    employee_notes = db.Column(db.Text, nullable=True)  # ملاحظات الموظف
    manager_notes = db.Column(db.Text, nullable=True)  # ملاحظات المدير
    
    # معلومات الموافقة
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # من وافق على المعاملة
    approved_at = db.Column(db.DateTime, nullable=True)  # تاريخ الموافقة
    
    # معلومات الإنشاء
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # من أنشأ المعاملة (نظام أو مستخدم)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # العلاقات
    employee = db.relationship('Employee', backref='absence_transactions')
    shift = db.relationship('Shift', backref='absence_transactions')
    approver = db.relationship('User', foreign_keys=[approved_by], backref='approved_absence_transactions')
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_absence_transactions')
    
    # العلاقة مع الإجابات
    answers = db.relationship('AbsenceAnswer', foreign_keys=[AbsenceAnswer.absence_transaction_id], back_populates='absence_transaction', lazy='dynamic')
    
    # قيود
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'approved', 'rejected')", name='check_status'),
    )
    
    def __repr__(self):
        return f"<AbsenceTransaction {self.transaction_number}>"
    
    def generate_transaction_number(self):
        """توليد رقم معاملة فريد"""
        from datetime import datetime
        date_str = datetime.now().strftime('%Y%m%d')
        count = AbsenceTransaction.query.filter(
            AbsenceTransaction.transaction_number.like(f'ABS-{date_str}-%')
        ).count()
        return f'ABS-{date_str}-{count + 1:04d}'
    
    def can_be_approved_by(self, user):
        """التحقق من إمكانية موافقة المستخدم على المعاملة"""
        if not self.employee:
            return False
            
        # السوبر أدمن يمكنه الموافقة على أي معاملة
        if user.is_super_admin():
            return True
        
        # التحقق من الصلاحيات حسب الهيكل التنظيمي
        employee = self.employee
        
        # رئيس الفرع أو نائبه
        if (user.is_branch_head() or user.is_branch_deputy()) and user.branch_id == employee.branch_id:
            return True
        
        # رئيس القسم أو نائبه
        if (user.is_department_head() or user.is_department_deputy()) and user.department_id == employee.department_id:
            return True
        
        return False
    
    def get_approvers(self):
        """الحصول على قائمة المستخدمين الذين يمكنهم الموافقة على المعاملة"""
        from app.models.user import User
        
        if not self.employee:
            return []
        
        approvers = []
        employee = self.employee
        
        # رؤساء ونواب الفرع
        if employee.branch_id:
            branch_managers = User.query.filter(
                User.branch_id == employee.branch_id,
                User.user_type.in_(['branch_head', 'branch_deputy']),
                User.is_active == True
            ).all()
            approvers.extend(branch_managers)
        
        # رؤساء ونواب القسم
        if employee.department_id:
            dept_managers = User.query.filter(
                User.department_id == employee.department_id,
                User.user_type.in_(['department_head', 'department_deputy']),
                User.is_active == True
            ).all()
            approvers.extend(dept_managers)
        
        # إضافة السوبر أدمن
        super_admins = User.query.filter(
            User.user_type == 'super_admin',
            User.is_active == True
        ).all()
        approvers.extend(super_admins)
        
        # إزالة التكرارات
        return list(set(approvers))

    def calculate_total_deductions(self):
        """حساب إجمالي الخصومات بناءً على الإجابات"""
        total = 0
        for answer in self.answers:
            if answer.is_answered:
                total += answer.question.deduction_value
        return total