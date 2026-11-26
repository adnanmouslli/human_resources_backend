from app import db
from datetime import datetime, date, timedelta, timezone
from sqlalchemy import CheckConstraint
import json

try:
    from zoneinfo import ZoneInfo
    _CAIRO_TZ = ZoneInfo('Africa/Cairo')
except Exception:  # pragma: no cover - أنظمة بلا zoneinfo/tzdata
    _CAIRO_TZ = timezone(timedelta(hours=2))

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
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, approved, rejected, cancelled
    
    # تفاصيل المعاملة (JSON)
    details = db.Column(db.Text, nullable=True)  # تخزين البيانات كـ JSON
    
    # ملاحظات عامة
    notes = db.Column(db.Text, nullable=True)
    reason_for_rejection = db.Column(db.Text, nullable=True)  # سبب الرفض / الإلغاء
    
    # تواريخ
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    approved_at = db.Column(db.DateTime, nullable=True)
    rejected_at = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    
    # العلاقات
    employee = db.relationship('Employee', backref='employee_transactions')
    requester = db.relationship('User', foreign_keys=[requested_by], backref='user_created_transactions')
    approvals = db.relationship('TransactionApproval', back_populates='transaction', lazy='dynamic', cascade='all, delete-orphan')
    
    # قيود
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name='check_transaction_status',
        ),
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
        """
        الحصول على قائمة المستخدمين المطلوب موافقتهم:
        - رؤساء ونواب فرع وقسم الموظف فقط (المدير العام ليس ضمن الموافقين، مثل حساب المطور dev).
        - لا يوافق أحد على معاملة تخصّه هو (حساب الموظف صاحب المعاملة مستبعد).
        - احتياط: إذا لم يوجد أي رئيس/نائب للموظف، يصبح المدير العام هو الموافق
          حتى لا تبقى المعاملة معلّقة للأبد.
        """
        from app.models.user import User

        if not self.employee:
            return []

        approvers = []
        employee = self.employee

        from app.models.user import UserBranchHead, UserDepartmentHead
        from app import db

        # رؤساء ونواب الفرع (جدول الربط + توافق الحقل القديم)
        if employee.branch_id:
            junction_branch = db.session.query(User).join(UserBranchHead).filter(
                UserBranchHead.branch_id == employee.branch_id,
                User.user_type.in_(['branch_head', 'branch_deputy']),
                User.is_active == True,
            ).all()
            legacy_branch = User.query.filter(
                User.branch_id == employee.branch_id,
                User.user_type.in_(['branch_head', 'branch_deputy']),
                User.is_active == True,
            ).all()
            by_id = {u.id: u for u in junction_branch + legacy_branch}
            approvers.extend(by_id.values())

        # رؤساء ونواب القسم (جدول الربط + توافق الحقل القديم)
        if employee.department_id:
            junction_dept = db.session.query(User).join(UserDepartmentHead).filter(
                UserDepartmentHead.department_id == employee.department_id,
                User.user_type.in_(['department_head', 'department_deputy']),
                User.is_active == True,
            ).all()
            legacy_dept = User.query.filter(
                User.department_id == employee.department_id,
                User.user_type.in_(['department_head', 'department_deputy']),
                User.is_active == True,
            ).all()
            by_id = {u.id: u for u in junction_dept + legacy_dept}
            approvers.extend(by_id.values())

        # استبعاد صاحب المعاملة نفسه (رئيس/نائب يطلب لنفسه)
        approvers = [u for u in approvers if u.employee_id != employee.id]

        # احتياط: لا يوجد رئيس أو نائب ← المدير العام
        if not approvers:
            approvers = User.query.filter(
                User.user_type == 'super_admin',
                User.is_active == True
            ).all()

        # إزالة التكرارات
        return list(set(approvers))

    def can_be_approved_by(self, user):
        """التحقق من إمكانية موافقة المستخدم على المعاملة: فقط من هو ضمن الموافقين المطلوبين."""
        if not self.employee or user is None:
            return False
        return any(u.id == user.id for u in self.get_required_approvers())
    
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

    def is_fully_rejected(self):
        """
        التحقق من رفض جميع الموافقين المطلوبين.
        رفض شخص واحد لا يرفض المعاملة؛ تبقى معلّقة ليُبدي الباقون رأيهم.
        """
        required_approvers = self.get_required_approvers()
        rejected_user_ids = [approval.approver_id for approval in self.approvals if approval.status == 'rejected']
        return len(required_approvers) > 0 and all(user.id in rejected_user_ids for user in required_approvers)

    def get_approval_of(self, user):
        """سجل موافقة مستخدم معيّن على هذه المعاملة (أو None)"""
        if user is None:
            return None
        return self.approvals.filter_by(approver_id=user.id).first()

    def collect_rejection_reasons(self):
        """تجميع أسباب الرفض من جميع الرافضين: «الاسم: السبب» في كل سطر"""
        reasons = []
        for approval in self.approvals.filter_by(status='rejected').order_by(TransactionApproval.rejected_at):
            if not approval.notes:
                continue
            approver = approval.approver
            name = (approver.employee.full_name if approver and approver.employee
                    else (approver.username if approver else ''))
            reasons.append(f'{name}: {approval.notes}' if name else approval.notes)
        return '\n'.join(reasons) or None

    def mark_rejected(self):
        """رفض المعاملة نهائياً (يُستدعى فقط عند رفض جميع الموافقين)"""
        self.status = 'rejected'
        self.rejected_at = datetime.now()
        self.reason_for_rejection = self.collect_rejection_reasons()

    def cancel(self, reason=None):
        """إلغاء معاملة معتمدة مع مزامنة السجل النهائي (إجازة/سلفة/…)."""
        if self.status != 'approved':
            raise ValueError('يمكن إلغاء المعاملات المعتمدة فقط')

        self.status = 'cancelled'
        self.cancelled_at = datetime.now()
        self.updated_at = datetime.now()
        if reason:
            self.reason_for_rejection = reason

        if self.transaction_type in ('daily_leave', 'hourly_leave'):
            from app.models.leave import Leave
            for leave in Leave.query.filter_by(transaction_id=self.id).all():
                leave.status = 'cancelled'
                leave.updated_at = datetime.now()
                if reason:
                    note = (leave.notes or '').strip()
                    leave.notes = f'{note}\n[إلغاء] {reason}'.strip() if note else f'[إلغاء] {reason}'
        elif self.transaction_type == 'advance':
            from app.models.advance import Advance
            Advance.query.filter_by(transaction_id=self.id).delete()
        elif self.transaction_type == 'reward':
            from app.models.reward import Reward
            Reward.query.filter_by(transaction_id=self.id).delete()
        elif self.transaction_type == 'penalty':
            from app.models.penalty import Penalty
            Penalty.query.filter_by(transaction_id=self.id).delete()

    def create_final_record(self):
        """إنشاء السجل النهائي في الجدول المناسب عند اكتمال الموافقات"""
        if not self.is_fully_approved():
            return False

        def parse_date_flexible(date_str):
            """
            تحليل تاريخ تقويمي بتوقيت القاهرة.
            - YYYY-MM-DD يُؤخذ كما هو (نية المستخدم المحلية).
            - ISO مع Z/إزاحة (مثل 2026-11-22T22:00:00.000Z) يُحوَّل إلى Africa/Cairo
              ثم يُؤخذ اليوم المحلي — يمنع إزاحة يوم عند إنشاء الإجازة من الويب.
            """
            if not date_str:
                return datetime.now(_CAIRO_TZ).date()
            if isinstance(date_str, datetime):
                if date_str.tzinfo is not None:
                    return date_str.astimezone(_CAIRO_TZ).date()
                return date_str.date()
            if isinstance(date_str, date):
                return date_str

            s = str(date_str).strip()
            if not s:
                return datetime.now(_CAIRO_TZ).date()

            # ISO datetime (مع أو بلا منطقة زمنية)
            if 'T' in s:
                try:
                    iso = s.replace('Z', '+00:00')
                    # من "....000+00:00" أزل كسور الثواني الزائدة إن لزم
                    if '.' in iso:
                        head, rest = iso.split('.', 1)
                        frac = ''
                        tz = ''
                        for i, ch in enumerate(rest):
                            if ch.isdigit():
                                frac += ch
                            else:
                                tz = rest[i:]
                                break
                        else:
                            tz = ''
                        frac = (frac + '000000')[:6]
                        iso = f'{head}.{frac}{tz}' if tz or frac else head
                    dt = datetime.fromisoformat(iso)
                    if dt.tzinfo is not None:
                        return dt.astimezone(_CAIRO_TZ).date()
                    return dt.date()
                except ValueError:
                    s = s.split('T')[0]
            elif ' ' in s:
                try:
                    dt = datetime.fromisoformat(s)
                    if dt.tzinfo is not None:
                        return dt.astimezone(_CAIRO_TZ).date()
                    return dt.date()
                except ValueError:
                    s = s.split(' ')[0]

            for date_format in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d'):
                try:
                    return datetime.strptime(s, date_format).date()
                except ValueError:
                    continue

            print(f"Warning: Could not parse date: {date_str}, using current date")
            return datetime.now(_CAIRO_TZ).date()
            
        
        details = self.get_details()
        
        try:
            if self.transaction_type == 'advance':
                from app.models.advance import Advance
                from app.services.advance_limit_service import AdvanceLimitError, validate_advance_request
                
                # استخدام الدالة المحسنة لتحليل التاريخ
                advance_date = parse_date_flexible(details.get('date'))
                amount = details.get('amount', 0)

                # إعادة فحص الحد عند الاعتماد النهائي (قد يتغير الاستهلاك بعد إنشاء الطلب)
                employee = self.employee
                if employee is None:
                    from app.models.employee import Employee
                    employee = Employee.query.get(self.employee_id)
                try:
                    validate_advance_request(
                        employee,
                        amount,
                        ref_date=advance_date,
                        exclude_transaction_id=self.id,
                    )
                except AdvanceLimitError as e:
                    raise Exception(e.message)
                
                advance = Advance(
                    date=advance_date,
                    employee_id=self.employee_id,
                    amount=amount,
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

                # السبب اختياري عند الإنشاء؛ لا نمنع الاعتماد بسبب فراغه
                reason = (details.get('reason') or self.notes or '').strip() or None

                leave_data = {
                    'employee_id': self.employee_id,
                    'leave_type': self.transaction_type,
                    'transaction_id': self.id,
                    'reason': reason,
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
                        start_date = parse_date_flexible(details.get('start_date'))
                        days = int(details.get('days', 1))
                        # إن وُجد end_date في التفاصيل استخدمه (بعد التحويل المحلي)، وإلا احسبه من الأيام
                        if details.get('end_date'):
                            end_date = parse_date_flexible(details.get('end_date'))
                            if end_date < start_date:
                                end_date = start_date
                            days = (end_date - start_date).days + 1
                        else:
                            end_date = start_date + timedelta(days=days - 1) if days > 1 else start_date
                        
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
        """
        الموافقة على المعاملة (أو تغيير رأي سابق بالرفض إلى موافقة).
        تُعتمد المعاملة فقط عند موافقة جميع الموافقين المطلوبين.
        """
        self.status = 'approved'
        self.notes = notes
        self.approved_at = datetime.now()
        self.rejected_at = None

         # التحقق من اكتمال جميع الموافقات
        if self.transaction.is_fully_approved():
            # هنا يتم استدعاء التابع لإنشاء السجل النهائي
            success = self.transaction.create_final_record()
            if not success:
                # في حالة فشل إنشاء السجل النهائي
                raise Exception("فشل في إنشاء السجل النهائي للمعاملة")

    def reject(self, notes=None):
        """
        رفض المعاملة من قِبل هذا الموافق (أو تغيير رأي سابق بالموافقة إلى رفض).
        لا تُرفض المعاملة نهائياً إلا إذا رفضها جميع الموافقين المطلوبين؛
        وإلا تبقى معلّقة ويستطيع الباقون إبداء رأيهم.
        """
        self.status = 'rejected'
        self.notes = notes
        self.rejected_at = datetime.now()
        self.approved_at = None

        if self.transaction.is_fully_rejected():
            self.transaction.mark_rejected()