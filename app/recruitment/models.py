# app/recruitment/models.py
# نماذج قسم التوظيف - 7 جداول

from app import db
from datetime import datetime


ALLOWED_FIELD_TYPES = [
    'text', 'textarea', 'number', 'date', 'select',
    'radio', 'checkbox', 'rating', 'experience_group', 'phone'
]

ALLOWED_STATUSES = ['new', 'under_review', 'interview', 'accepted', 'rejected']


class RecruitmentFormSection(db.Model):
    """أقسام نموذج التوظيف - مجموعات الحقول"""
    __tablename__ = 'recruitment_form_sections'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)          # اسم القسم، مثل: "المعلومات الشخصية"
    display_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    # العلاقات
    fields = db.relationship(
        'RecruitmentFormField',
        backref='section',
        lazy='dynamic',
        cascade='all, delete-orphan',
        order_by='RecruitmentFormField.display_order'
    )

    def to_dict(self, include_fields=False):
        data = {
            'id': self.id,
            'name': self.name,
            'display_order': self.display_order,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        if include_fields:
            data['fields'] = [f.to_dict() for f in self.fields.filter_by(is_active=True)]
        return data

    def __repr__(self):
        return f"<RecruitmentFormSection {self.name}>"


class RecruitmentFormField(db.Model):
    """حقول نموذج التوظيف - تعريف كل حقل قابل للتكوين"""
    __tablename__ = 'recruitment_form_fields'

    id = db.Column(db.Integer, primary_key=True)
    section_id = db.Column(db.Integer, db.ForeignKey('recruitment_form_sections.id', ondelete='CASCADE'), nullable=False)

    # المفتاح الآلي للحقل (فريد)
    field_key = db.Column(db.String(100), unique=True, nullable=False)
    # التسمية العربية للعرض
    label = db.Column(db.String(200), nullable=False)
    # نوع الحقل
    field_type = db.Column(db.String(50), nullable=False)
    # خيارات الحقل (JSON) للـ select و radio
    options = db.Column(db.Text, nullable=True)

    is_required = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, nullable=False, default=0)

    # ربط بعمود في جدول الموظفين عند التعيين
    maps_to_employee_field = db.Column(db.String(100), nullable=True)
    # هل يظهر كفلتر في قائمة الطلبات
    is_searchable = db.Column(db.Boolean, default=False)
    # حقل أساسي لا يمكن حذفه
    is_system_field = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # العلاقات
    answers = db.relationship(
        'RecruitmentApplicationAnswer',
        backref='field',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    def to_dict(self):
        import json
        options = None
        if self.options:
            try:
                options = json.loads(self.options)
            except Exception:
                options = self.options
        return {
            'id': self.id,
            'section_id': self.section_id,
            'field_key': self.field_key,
            'label': self.label,
            'field_type': self.field_type,
            'options': options,
            'is_required': self.is_required,
            'is_active': self.is_active,
            'display_order': self.display_order,
            'maps_to_employee_field': self.maps_to_employee_field,
            'is_searchable': self.is_searchable,
            'is_system_field': self.is_system_field,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<RecruitmentFormField {self.field_key}>"


class RecruitmentApplication(db.Model):
    """طلبات التوظيف - سجل واحد لكل متقدم"""
    __tablename__ = 'recruitment_applications'

    id = db.Column(db.Integer, primary_key=True)
    applied_position = db.Column(db.String(255), nullable=False)     # الوظيفة المتقدم إليها
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)

    status = db.Column(db.String(50), default='new', nullable=False)
    rejection_reason = db.Column(db.Text, nullable=True)
    evaluation_score = db.Column(db.Float, nullable=True)             # تقييم عام 1.0-5.0

    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # العلاقات
    branch = db.relationship('Branch', foreign_keys=[branch_id], lazy='joined')
    department = db.relationship('Department', foreign_keys=[department_id], lazy='joined')
    creator = db.relationship('User', foreign_keys=[created_by], lazy='joined')

    answers = db.relationship(
        'RecruitmentApplicationAnswer',
        backref='application',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    experiences = db.relationship(
        'RecruitmentApplicationExperience',
        backref='application',
        lazy='dynamic',
        cascade='all, delete-orphan',
        order_by='RecruitmentApplicationExperience.experience_order'
    )
    hiring_decision = db.relationship(
        'HiringDecision',
        backref='application',
        uselist=False,
        cascade='all, delete-orphan'
    )

    def to_dict(self, include_answers=False, include_experiences=False, include_hiring=False):
        data = {
            'id': self.id,
            'applied_position': self.applied_position,
            'branch_id': self.branch_id,
            'branch': self.branch.name if self.branch else None,
            'department_id': self.department_id,
            'department': self.department.name if self.department else None,
            'status': self.status,
            'rejection_reason': self.rejection_reason,
            'evaluation_score': self.evaluation_score,
            'created_by': self.created_by,
            'creator_username': self.creator.username if self.creator else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_answers:
            data['answers'] = {
                a.field.field_key: {
                    'label': a.field.label,
                    'value': a.value,
                    'field_type': a.field.field_type,
                    'section': a.field.section.name if a.field.section else None
                }
                for a in self.answers.join(RecruitmentFormField).all()
            }
        if include_experiences:
            data['experiences'] = [e.to_dict() for e in self.experiences.all()]
        if include_hiring and self.hiring_decision:
            data['hiring_decision'] = self.hiring_decision.to_dict()
        return data

    def __repr__(self):
        return f"<RecruitmentApplication {self.id} - {self.applied_position}>"


class RecruitmentApplicationAnswer(db.Model):
    """إجابات طلبات التوظيف - نمط EAV"""
    __tablename__ = 'recruitment_application_answers'

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(
        db.Integer,
        db.ForeignKey('recruitment_applications.id', ondelete='CASCADE'),
        nullable=False
    )
    field_id = db.Column(
        db.Integer,
        db.ForeignKey('recruitment_form_fields.id'),
        nullable=False
    )
    value = db.Column(db.Text, nullable=True)   # كل القيم مخزنة كنص

    __table_args__ = (
        db.UniqueConstraint('application_id', 'field_id', name='uq_application_field'),
        db.Index('ix_application_answers_app_field', 'application_id', 'field_id'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'application_id': self.application_id,
            'field_id': self.field_id,
            'field_key': self.field.field_key if self.field else None,
            'value': self.value,
        }

    def __repr__(self):
        return f"<RecruitmentApplicationAnswer app={self.application_id} field={self.field_id}>"


class RecruitmentApplicationExperience(db.Model):
    """خبرات المتقدمين - كتلة قابلة للتكرار"""
    __tablename__ = 'recruitment_application_experiences'

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(
        db.Integer,
        db.ForeignKey('recruitment_applications.id', ondelete='CASCADE'),
        nullable=False
    )
    experience_order = db.Column(db.Integer, nullable=False, default=1)  # 1, 2, 3...

    company_name = db.Column(db.String(255), nullable=True)      # عمل سابق
    company_field = db.Column(db.String(255), nullable=True)     # مجال الشركة
    position = db.Column(db.String(255), nullable=True)          # الوظيفة
    duration = db.Column(db.String(100), nullable=True)          # مدة العمل
    hours_per_day = db.Column(db.String(20), nullable=True)      # ساعات
    salary = db.Column(db.String(50), nullable=True)             # المرتب
    reason_for_leaving = db.Column(db.Text, nullable=True)       # سبب ترك العمل

    def to_dict(self):
        return {
            'id': self.id,
            'application_id': self.application_id,
            'experience_order': self.experience_order,
            'company_name': self.company_name,
            'company_field': self.company_field,
            'position': self.position,
            'duration': self.duration,
            'hours_per_day': self.hours_per_day,
            'salary': self.salary,
            'reason_for_leaving': self.reason_for_leaving,
        }

    def __repr__(self):
        return f"<RecruitmentApplicationExperience app={self.application_id} order={self.experience_order}>"


class HiringDecision(db.Model):
    """قرارات التعيين النهائية"""
    __tablename__ = 'hiring_decisions'

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(
        db.Integer,
        db.ForeignKey('recruitment_applications.id', ondelete='CASCADE'),
        unique=True,
        nullable=False
    )

    # بيانات التعيين الأساسية
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    job_title_id = db.Column(db.Integer, db.ForeignKey('job_titles.id'), nullable=True)  # ربط بالمسمى الوظيفي
    salary = db.Column(db.Numeric(10, 2), nullable=True)
    start_date = db.Column(db.Date, nullable=True)

    # نوع الموظف ونظام العمل
    employee_type = db.Column(db.String(50), nullable=True, default='permanent')  # permanent | temporary
    work_system = db.Column(db.String(100), nullable=True)  # نظام العمل حسب المسمى الوظيفي
    shift_id = db.Column(db.Integer, db.ForeignKey('shift.id'), nullable=True)  # الوردية (إذا كان نظام ورديات)
    profession_id = db.Column(db.Integer, db.ForeignKey('professions.id'), nullable=True)  # المهنة (للمؤقتين)
    fingerprint_id = db.Column(db.String(50), nullable=True)  # رقم البصمة

    # بيانات إضافية
    probation_salary = db.Column(db.Numeric(10, 2), nullable=True)   # مرتب فترة التجربة
    working_hours = db.Column(db.String(50), nullable=True)           # ساعات دوام
    notes = db.Column(db.Text, nullable=True)                         # ملاحظات

    decided_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    decided_at = db.Column(db.DateTime, default=datetime.now)

    # معرف الموظف المنشأ بعد القبول
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)

    # العلاقات
    department = db.relationship('Department', foreign_keys=[department_id], lazy='joined')
    branch = db.relationship('Branch', foreign_keys=[branch_id], lazy='joined')
    job_title = db.relationship('JobTitle', foreign_keys=[job_title_id], lazy='joined')
    shift = db.relationship('Shift', foreign_keys=[shift_id], lazy='joined')
    profession = db.relationship('Profession', foreign_keys=[profession_id], lazy='joined')
    decider = db.relationship('User', foreign_keys=[decided_by], lazy='joined')
    employee = db.relationship('Employee', foreign_keys=[employee_id], lazy='joined')

    def to_dict(self):
        return {
            'id': self.id,
            'application_id': self.application_id,
            'branch_id': self.branch_id,
            'branch': self.branch.name if self.branch else None,
            'department_id': self.department_id,
            'department': self.department.name if self.department else None,
            'job_title_id': self.job_title_id,
            'job_title': self.job_title.title_name if self.job_title else None,
            'salary': float(self.salary) if self.salary else None,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'employee_type': self.employee_type,
            'work_system': self.work_system,
            'shift_id': self.shift_id,
            'shift': self.shift.name if self.shift else None,
            'profession_id': self.profession_id,
            'profession': self.profession.name if self.profession else None,
            'fingerprint_id': self.fingerprint_id,
            'probation_salary': float(self.probation_salary) if self.probation_salary else None,
            'working_hours': self.working_hours,
            'notes': self.notes,
            'decided_by': self.decided_by,
            'decider_username': self.decider.username if self.decider else None,
            'decided_at': self.decided_at.isoformat() if self.decided_at else None,
            'employee_id': self.employee_id,
        }

    def __repr__(self):
        return f"<HiringDecision app={self.application_id}>"


class HeadcountTarget(db.Model):
    """أهداف الاستيعاب الوظيفي لكل فرع/قسم"""
    __tablename__ = 'headcount_targets'

    id = db.Column(db.Integer, primary_key=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)

    target_count = db.Column(db.Integer, nullable=False)
    warning_threshold = db.Column(db.Integer, default=1)    # أرسل تنبيهاً عند النقص >= هذا
    notes = db.Column(db.Text, nullable=True)

    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # العلاقات
    branch = db.relationship('Branch', foreign_keys=[branch_id], lazy='joined')
    department = db.relationship('Department', foreign_keys=[department_id], lazy='joined')
    creator = db.relationship('User', foreign_keys=[created_by], lazy='joined')

    __table_args__ = (
        db.UniqueConstraint('branch_id', 'department_id', name='uq_headcount_branch_dept'),
        db.CheckConstraint(
            'branch_id IS NOT NULL OR department_id IS NOT NULL',
            name='ck_headcount_branch_or_dept'
        ),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'branch_id': self.branch_id,
            'branch': self.branch.name if self.branch else None,
            'department_id': self.department_id,
            'department': self.department.name if self.department else None,
            'target_count': self.target_count,
            'warning_threshold': self.warning_threshold,
            'notes': self.notes,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<HeadcountTarget branch={self.branch_id} dept={self.department_id} target={self.target_count}>"
