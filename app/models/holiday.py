from app import db
from datetime import datetime

class Holiday(db.Model):
    """
    نموذج العطل: يمثل العطل الرسمية والإجازات المحددة من قبل الإدارة
    """
    __tablename__ = 'holidays'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)  # اسم العطلة
    date = db.Column(db.Date, nullable=False)  # تاريخ العطلة
    description = db.Column(db.Text, nullable=True)  # وصف العطلة
    
    # نوع العطلة: 'religious', 'national', 'company', 'emergency'
    holiday_type = db.Column(db.String(50), default='national')
    
    # هل العطلة مدفوعة الأجر أم لا
    is_paid = db.Column(db.Boolean, default=True)
    
    # فرع محدد (إذا كانت العطلة خاصة بفرع معين)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    
    # قسم محدد (إذا كانت العطلة خاصة بقسم معين)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    
    # هل العطلة نشطة
    is_active = db.Column(db.Boolean, default=True)
    
    # من أنشأ العطلة
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # تواريخ النظام
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f"<Holiday {self.name} on {self.date}>"
    
    @classmethod
    def is_holiday(cls, date, branch_id=None, department_id=None):
        """
        التحقق من كون التاريخ المحدد يوم عطلة
        """
        query = cls.query.filter(
            cls.date == date,
            cls.is_active == True
        )
        
        # إضافة فلاتر الفرع والقسم إذا وجدت
        if branch_id:
            query = query.filter(
                db.or_(
                    cls.branch_id == branch_id,
                    cls.branch_id.is_(None)  # العطل العامة لجميع الفروع
                )
            )
        
        if department_id:
            query = query.filter(
                db.or_(
                    cls.department_id == department_id,
                    cls.department_id.is_(None)  # العطل العامة لجميع الأقسام
                )
            )
        
        return query.first()
    
    @classmethod
    def get_holidays_in_period(cls, start_date, end_date, branch_id=None, department_id=None):
        """
        الحصول على جميع العطل في فترة محددة
        """
        query = cls.query.filter(
            cls.date.between(start_date, end_date),
            cls.is_active == True
        )
        
        if branch_id:
            query = query.filter(
                db.or_(
                    cls.branch_id == branch_id,
                    cls.branch_id.is_(None)
                )
            )
        
        if department_id:
            query = query.filter(
                db.or_(
                    cls.department_id == department_id,
                    cls.department_id.is_(None)
                )
            )
        
        return query.order_by(cls.date).all()
    
    def to_dict(self):
        """تحويل البيانات إلى قاموس"""
        return {
            'id': self.id,
            'name': self.name,
            'date': self.date.isoformat(),
            'description': self.description,
            'holiday_type': self.holiday_type,
            'is_paid': self.is_paid,
            'branch_id': self.branch_id,
            'department_id': self.department_id,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }