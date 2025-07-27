from app import db
from datetime import datetime, date, timedelta
from sqlalchemy import CheckConstraint

class Leave(db.Model):
    """
    جدول الإجازات
    """
    __tablename__ = 'leaves'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # معرف الموظف
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    
    # نوع الإجازة
    leave_type = db.Column(db.String(50), nullable=False)  # hourly_leave, daily_leave
    
    # تاريخ بداية الإجازة
    start_date = db.Column(db.Date, nullable=False)
    
    # تاريخ نهاية الإجازة (للإجازات اليومية فقط)
    end_date = db.Column(db.Date, nullable=True)
    
    # وقت بداية الإجازة (للإجازات الساعية فقط)
    start_time = db.Column(db.Time, nullable=True)
    
    # وقت نهاية الإجازة (للإجازات الساعية فقط)
    end_time = db.Column(db.Time, nullable=True)
    
    # عدد الساعات (للإجازات الساعية)
    hours = db.Column(db.Integer, nullable=True)
    
    # عدد الأيام (للإجازات اليومية)
    days = db.Column(db.Integer, nullable=True)
    
    # سبب الإجازة
    reason = db.Column(db.Text, nullable=True)
    
    # ملاحظات
    notes = db.Column(db.Text, nullable=True)
    
    # معرف المعاملة المرتبطة
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=True)
    
    # حالة الإجازة
    status = db.Column(db.String(20), nullable=False, default='active')  # active, cancelled, expired
    
    # تواريخ
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # العلاقات
    employee = db.relationship('Employee', backref='employee_leaves')
    
     # إضافة حقل جديد للربط مع نظام المعاملات
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=True)
    
    # علاقة مع المعاملة
    transaction = db.relationship('Transaction', backref='leave_record')


    # قيود
    __table_args__ = (
        CheckConstraint("leave_type IN ('hourly_leave', 'daily_leave')", name='check_leave_type'),
        CheckConstraint("status IN ('active', 'cancelled', 'expired')", name='check_leave_status'),
    )
    
    def __repr__(self):
        return f"<Leave {self.id} - {self.employee.full_name} - {self.leave_type}>"
    
    def is_date_covered_by_leave(self, check_date):
        """
        فحص ما إذا كان التاريخ المحدد مغطى بهذه الإجازة
        """
        if self.status != 'active':
            return False
            
        if self.leave_type == 'daily_leave':
            return self.start_date <= check_date <= (self.end_date or self.start_date)
        elif self.leave_type == 'hourly_leave':
            return self.start_date == check_date
        
        return False
    
    def is_time_covered_by_leave(self, check_date, check_time):
        """
        فحص ما إذا كان الوقت المحدد في التاريخ المحدد مغطى بالإجازة الساعية
        """
        if self.status != 'active' or self.leave_type != 'hourly_leave':
            return False
            
        if self.start_date == check_date:
            if self.start_time and self.end_time:
                return self.start_time <= check_time <= self.end_time
        
        return False
    
    def get_leave_details(self):
        """
        الحصول على تفاصيل الإجازة
        """
        details = {
            'id': self.id,
            'employee_id': self.employee_id,
            'employee_name': self.employee.full_name,
            'leave_type': self.leave_type,
            'start_date': self.start_date.isoformat(),
            'reason': self.reason,
            'notes': self.notes,
            'status': self.status,
            'transaction_id': self.transaction_id,
            'created_at': self.created_at.isoformat()
        }
        
        if self.leave_type == 'daily_leave':
            details.update({
                'end_date': self.end_date.isoformat() if self.end_date else None,
                'days': self.days
            })
        elif self.leave_type == 'hourly_leave':
            details.update({
                'start_time': self.start_time.isoformat() if self.start_time else None,
                'end_time': self.end_time.isoformat() if self.end_time else None,
                'hours': self.hours
            })
        
        return details
    
    @classmethod
    def get_employee_leaves_for_period(cls, employee_id, start_date, end_date):
        """
        الحصول على إجازات الموظف لفترة محددة
        """
        return cls.query.filter(
            cls.employee_id == employee_id,
            cls.status == 'active',
            cls.start_date <= end_date,
            db.or_(
                cls.end_date >= start_date,
                cls.end_date.is_(None)
            )
        ).all()
    
    @classmethod
    def get_employee_leaves_for_date(cls, employee_id, check_date):
        """
        الحصول على إجازات الموظف لتاريخ محدد
        """
        return cls.query.filter(
            cls.employee_id == employee_id,
            cls.status == 'active',
            cls.start_date <= check_date,
            db.or_(
                cls.end_date >= check_date,
                cls.end_date.is_(None)
            )
        ).all()