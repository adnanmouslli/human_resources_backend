from app import db
from datetime import datetime, timedelta
from sqlalchemy import CheckConstraint
import json

class Transaction(db.Model):
    """
    جدول المعاملات الموحد
    """
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    transaction_number = db.Column(db.String(50), nullable=False, unique=True)  # رقم المعاملة
    
    # نوع المعاملة
    transaction_type = db.Column(db.String(50), nullable=False)  # advance, reward, penalty, hourly_leave, daily_leave
    
    # الموظف المطلوب له المعاملة
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    
    # من طلب المعاملة
    requested_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # حالة المعاملة
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, approved, rejected
    
    # تفاصيل المعاملة (JSON)
    details = db.Column(db.Text, nullable=True)  # تخزين البيانات كـ JSON
    
    # ملاحظات عامة
    notes = db.Column(db.Text, nullable=True)
    reason_for_rejection = db.Column(db.Text, nullable=True)  # سبب الرفض
    
    # تواريخ
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    approved_at = db.Column(db.DateTime, nullable=True)
    rejected_at = db.Column(db.DateTime, nullable=True)
    
    # العلاقات
    employee = db.relationship('Employee', backref='employee_transactions')
    requester = db.relationship('User', foreign_keys=[requested_by], backref='user_created_transactions')
    approvals = db.relationship('TransactionApproval', back_populates='transaction', lazy='dynamic', cascade='all, delete-orphan')
    
    # قيود
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'approved', 'rejected')", name='check_transaction_status'),
        CheckConstraint("transaction_type IN ('advance', 'reward', 'penalty', 'hourly_leave', 'daily_leave')", name='check_transaction_type'),
    )
    
    def __repr__(self):
        return f"<Transaction {self.transaction_number} - {self.transaction_type}>"
    
    def generate_transaction_number(self):
        """توليد رقم معاملة فريد"""
        type_prefix = {
            'advance': 'ADV',
            'reward': 'RWD', 
            'penalty': 'PEN',
            'hourly_leave': 'HLV',
            'daily_leave': 'DLV'
        }.get(self.transaction_type, 'TRX')
        
        date_str = datetime.now().strftime('%Y%m%d')
        count = Transaction.query.filter(
            Transaction.transaction_number.like(f'{type_prefix}-{date_str}-%')
        ).count()
        return f'{type_prefix}-{date_str}-{count + 1:04d}'
    
    def get_details(self):
        """الحصول على تفاصيل المعاملة"""
        if self.details:
            try:
                return json.loads(self.details)
            except:
                return {}
        return {}
    
    def set_details(self, details_dict):
        """تعيين تفاصيل المعاملة"""
        self.details = json.dumps(details_dict, ensure_ascii=False)
    
    def get_required_approvers(self):
        """الحصول على قائمة المستخدمين المطلوب موافقتهم"""
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
    
    def can_be_approved_by(self, user):
        """التحقق من إمكانية موافقة المستخدم على المعاملة"""
        if not self.employee:
            return False
            
        # السوبر أدمن يمكنه الموافقة على أي معاملة
        if user.is_super_admin():
            return True
        
        employee = self.employee
        
        # رئيس الفرع أو نائبه
        if (user.is_branch_head() or user.is_branch_deputy()) and user.branch_id == employee.branch_id:
            return True
        
        # رئيس القسم أو نائبه
        if (user.is_department_head() or user.is_department_deputy()) and user.department_id == employee.department_id:
            return True
        
        return False
    
    def get_pending_approvers(self):
        """الحصول على المستخدمين الذين لم يوافقوا بعد"""
        required_approvers = self.get_required_approvers()
        approved_user_ids = [approval.approver_id for approval in self.approvals if approval.status == 'approved']
        return [user for user in required_approvers if user.id not in approved_user_ids]
    
    def is_fully_approved(self):
        """التحقق من اكتمال الموافقات"""
        required_approvers = self.get_required_approvers()
        approved_user_ids = [approval.approver_id for approval in self.approvals if approval.status == 'approved']
        return len(required_approvers) > 0 and all(user.id in approved_user_ids for user in required_approvers)
    
    def has_any_rejection(self):
        """التحقق من وجود أي رفض"""
        return self.approvals.filter_by(status='rejected').first() is not None
    
    
    

     
    def create_final_record(self):
        """إنشاء السجل النهائي في الجدول المناسب عند اكتمال الموافقات"""
        if not self.is_fully_approved():
            return False

        def parse_date_flexible(date_str):
            """
            دالة مساعدة لتحليل التاريخ بتنسيقات مختلفة
            تدعم التنسيقات التالية:
            - YYYY-MM-DD
            - YYYY-MM-DDTHH:MM:SS.sssZ (ISO format)
            - YYYY-MM-DD HH:MM:SS
            """
            if not date_str:
                return datetime.now().date()
            
            # إذا كان التاريخ يحتوي على وقت، استخرج التاريخ فقط
            if 'T' in date_str:
                date_str = date_str.split('T')[0]
            elif ' ' in date_str:
                date_str = date_str.split(' ')[0]
            
            # قائمة التنسيقات المدعومة للتاريخ
            date_formats = [
                '%Y-%m-%d',         # 2025-07-28
                '%d/%m/%Y',         # 28/07/2025
                '%d-%m-%Y',         # 28-07-2025
                '%Y/%m/%d',         # 2025/07/28
            ]
            
            for date_format in date_formats:
                try:
                    return datetime.strptime(date_str, date_format).date()
                except ValueError:
                    continue
            
            # إذا فشل جميع التنسيقات، ارجع التاريخ الحالي
            print(f"Warning: Could not parse date: {date_str}, using current date")
            return datetime.now().date()
            
        
        details = self.get_details()
        
        try:
            if self.transaction_type == 'advance':
                from app.models.advance import Advance
                
                # استخدام الدالة المحسنة لتحليل التاريخ
                advance_date = parse_date_flexible(details.get('date'))
                
                advance = Advance(
                    date=advance_date,
                    employee_id=self.employee_id,
                    amount=details.get('amount', 0),
                    document_number=details.get('document_number', self.transaction_number),
                    notes=details.get('notes', self.notes),
                    transaction_id=self.id
                )
                db.session.add(advance)
                
            elif self.transaction_type == 'reward':
                from app.models.reward import Reward
                
                # استخدام الدالة المحسنة لتحليل التاريخ
                reward_date = parse_date_flexible(details.get('date'))
                
                reward = Reward(
                    date=reward_date,
                    employee_id=self.employee_id,
                    amount=details.get('amount', 0),
                    document_number=details.get('document_number', self.transaction_number),
                    notes=details.get('notes', self.notes),
                    transaction_id=self.id
                )
                db.session.add(reward)
                
            elif self.transaction_type == 'penalty':
                from app.models.penalty import Penalty
                
                # استخدام الدالة المحسنة لتحليل التاريخ
                penalty_date = parse_date_flexible(details.get('date'))
                
                penalty = Penalty(
                    date=penalty_date,
                    employee_id=self.employee_id,
                    amount=details.get('amount', 0),
                    document_number=details.get('document_number', self.transaction_number),
                    notes=details.get('notes', self.notes),
                    transaction_id=self.id
                )
                db.session.add(penalty)
                
            elif self.transaction_type in ['hourly_leave', 'daily_leave']:
                from app.models.leave import Leave
                
                # التحقق من البيانات المطلوبة
                if not details.get('reason'):
                    print("Error: Missing reason in transaction details")
                    return False
                
                leave_data = {
                    'employee_id': self.employee_id,
                    'leave_type': self.transaction_type,
                    'transaction_id': self.id,
                    'reason': details.get('reason'),
                    'notes': self.notes,
                    'status': 'active'
                }
                
                if self.transaction_type == 'hourly_leave':
                    # التحقق من البيانات المطلوبة للإجازة الساعية
                    if not details.get('leave_date') or not details.get('hours'):
                        print(f"Error: Missing required fields for hourly leave. Details: {details}")
                        return False
                    
                    try:
                        # تحليل تاريخ الإجازة باستخدام الدالة المحسنة
                        leave_date = parse_date_flexible(details.get('leave_date'))
                        
                        leave_data.update({
                            'start_date': leave_date,
                            'hours': int(details.get('hours'))
                        })
                        
                        # تحليل أوقات البداية والنهاية مع دعم تنسيقات متعددة
                        def parse_time_flexible(time_str):
                            """دالة مساعدة لتحليل الوقت بتنسيقات مختلفة"""
                            if not time_str:
                                return None
                            
                            # إزالة المنطقة الزمنية والأجزاء الإضافية
                            time_str = time_str.replace('Z', '').replace('T', ' ')
                            
                            # قائمة التنسيقات المدعومة
                            time_formats = [
                                '%H:%M:%S.%f',      # 07:00:00.000
                                '%H:%M:%S',         # 07:00:00
                                '%H:%M',            # 07:00
                                '%Y-%m-%d %H:%M:%S.%f',  # 2024-01-01 07:00:00.000
                                '%Y-%m-%d %H:%M:%S',     # 2024-01-01 07:00:00
                                '%Y-%m-%d %H:%M',        # 2024-01-01 07:00
                            ]
                            
                            for time_format in time_formats:
                                try:
                                    parsed_datetime = datetime.strptime(time_str, time_format)
                                    return parsed_datetime.time()
                                except ValueError:
                                    continue
                            
                            # إذا فشل جميع التنسيقات، جرب استخراج الوقت من سلسلة نصية
                            try:
                                # محاولة استخراج الوقت من نص مثل "2024-01-01T07:00:00.000Z"
                                if ' ' in time_str:
                                    time_part = time_str.split(' ')[1]
                                else:
                                    time_part = time_str
                                
                                # إزالة الأجزاء الإضافية
                                time_part = time_part.split('.')[0]  # إزالة الميلي ثانية
                                
                                return datetime.strptime(time_part, '%H:%M:%S').time()
                            except:
                                print(f"Warning: Could not parse time: {time_str}")
                                return None
                        
                        # تحليل أوقات البداية والنهاية
                        if details.get('start_time'):
                            leave_data['start_time'] = parse_time_flexible(details.get('start_time'))
                        
                        if details.get('end_time'):
                            leave_data['end_time'] = parse_time_flexible(details.get('end_time'))
                            
                    except (ValueError, TypeError) as e:
                        print(f"Error parsing hourly leave data: {str(e)}")
                        return False
                        
                elif self.transaction_type == 'daily_leave':
                    # التحقق من البيانات المطلوبة للإجازة اليومية
                    if not details.get('start_date') or not details.get('days'):
                        print(f"Error: Missing required fields for daily leave. Details: {details}")
                        return False
                    
                    try:
                        # تحليل تاريخ البداية باستخدام الدالة المحسنة
                        start_date = parse_date_flexible(details.get('start_date'))
                        days = int(details.get('days', 1))
                        end_date = start_date + timedelta(days=days-1) if days > 1 else start_date
                        
                        leave_data.update({
                            'start_date': start_date,
                            'end_date': end_date,
                            'days': days
                        })
                    except (ValueError, TypeError) as e:
                        print(f"Error parsing daily leave data: {str(e)}")
                        return False
                
                # إنشاء سجل الإجازة
                try:
                    print(f"Attempting to create Leave record with data: {leave_data}")
                    leave = Leave(**leave_data)
                    db.session.add(leave)
                    print(f"Leave record created successfully: {leave_data}")
                except Exception as e:
                    print(f"Error creating Leave object: {str(e)}")
                    print(f"Leave data that caused error: {leave_data}")
                    return False
            
            # تحديث حالة المعاملة
            self.status = 'approved'
            self.approved_at = datetime.now()
            
            # حفظ التغييرات
            db.session.commit()
            print(f"Transaction {self.transaction_number} approved and final record created successfully")
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating final record for transaction {self.transaction_number}: {str(e)}")
            print(f"Transaction details: {details}")
            return False
            
     

class TransactionApproval(db.Model):
    """
    جدول موافقات المعاملات
    """
    __tablename__ = 'transaction_approvals'
    
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=False)
    approver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, approved, rejected
    notes = db.Column(db.Text, nullable=True)  # ملاحظات الموافق
    
    approved_at = db.Column(db.DateTime, nullable=True)
    rejected_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # العلاقات
    transaction = db.relationship('Transaction', back_populates='approvals')
    approver = db.relationship('User', foreign_keys=[approver_id], backref='user_given_approvals')
    
    # قيود
    __table_args__ = (
    CheckConstraint("status IN ('pending', 'approved', 'rejected')", name='check_approval_status'),
    db.UniqueConstraint('transaction_id', 'approver_id', name='unique_transaction_approver'),
    )
    
    def __repr__(self):
        return f"<TransactionApproval {self.transaction_id} by {self.approver_id}>"
    
    def approve(self, notes=None):
        """الموافقة على المعاملة"""
        self.status = 'approved'
        self.notes = notes
        self.approved_at = datetime.now()
        
         # التحقق من اكتمال جميع الموافقات
        if self.transaction.is_fully_approved():
            # هنا يتم استدعاء التابع لإنشاء السجل النهائي
            success = self.transaction.create_final_record()
            if not success:
                # في حالة فشل إنشاء السجل النهائي
                raise Exception("فشل في إنشاء السجل النهائي للمعاملة")
    
    def reject(self, notes=None):
        """رفض المعاملة"""
        self.status = 'rejected'
        self.notes = notes
        self.rejected_at = datetime.now()
        
        # تحديث حالة المعاملة إلى مرفوضة
        self.transaction.status = 'rejected'
        self.transaction.rejected_at = datetime.now()
        self.transaction.reason_for_rejection = notes