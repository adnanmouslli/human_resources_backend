# app/models/kpi.py
# نماذج موديول KPI - تقييم الأداء الوظيفي

from app import db
from datetime import datetime


class KpiTemplate(db.Model):
    """
    قالب KPI: مجموعة معايير تقييم مرتبطة بمسمى وظيفي معين.
    كل شركة تُنشئ قوالبها الخاصة بشكل ديناميكي.
    """
    __tablename__ = 'kpi_templates'

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    job_title_id = db.Column(db.Integer, db.ForeignKey('job_titles.id'), nullable=True)
    name        = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_active   = db.Column(db.Boolean, default=True)
    created_by  = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    created_at  = db.Column(db.DateTime, default=datetime.now)
    updated_at  = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # العلاقات
    job_title   = db.relationship('JobTitle', backref=db.backref('kpi_templates', lazy='dynamic'))
    creator     = db.relationship('Employee', foreign_keys=[created_by], backref=db.backref('created_kpi_templates', lazy='dynamic'))
    sections    = db.relationship('KpiSection', backref='template', lazy='dynamic', cascade='all, delete-orphan')
    criteria    = db.relationship('KpiCriterion', backref='template', lazy='dynamic', cascade='all, delete-orphan')
    assignments = db.relationship('KpiEmployeeAssignment', backref='template', lazy='dynamic')

    def __repr__(self):
        return f'<KpiTemplate {self.name}>'

    def to_dict(self, include_sections=False):
        data = {
            'id': self.id,
            'job_title_id': self.job_title_id,
            'job_title_name': self.job_title.title_name if self.job_title else None,
            'name': self.name,
            'description': self.description,
            'is_active': self.is_active,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'criteria_count': self.criteria.count(),
            'max_daily_score': sum(float(c.max_score) for c in self.criteria.all()),
        }
        if include_sections:
            data['sections'] = [s.to_dict(include_criteria=True) for s in self.sections.order_by(KpiSection.sort_order).all()]
        return data


class KpiSection(db.Model):
    """
    قسم داخل قالب KPI (مثل: الإنتاجية، السلوك، الحضور).
    يُستخدم لتنظيم المعايير في مجموعات منطقية.
    """
    __tablename__ = 'kpi_sections'

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    template_id = db.Column(db.Integer, db.ForeignKey('kpi_templates.id', ondelete='CASCADE'), nullable=False)
    name        = db.Column(db.String(150), nullable=False)
    sort_order  = db.Column(db.Integer, default=0)
    created_at  = db.Column(db.DateTime, default=datetime.now)
    updated_at  = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    criteria    = db.relationship('KpiCriterion', backref='section', lazy='dynamic',
                                  cascade='all, delete-orphan')

    def __repr__(self):
        return f'<KpiSection {self.name}>'

    def to_dict(self, include_criteria=False):
        data = {
            'id': self.id,
            'template_id': self.template_id,
            'name': self.name,
            'sort_order': self.sort_order,
        }
        if include_criteria:
            data['criteria'] = [c.to_dict() for c in self.criteria.order_by(KpiCriterion.sort_order).all()]
        return data


class KpiCriterion(db.Model):
    """
    معيار تقييم واحد داخل قسم.
    يحتوي على الدرجة القصوى وتكرار التقييم (يومي، أسبوعي، إلخ).
    """
    __tablename__ = 'kpi_criteria'

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    section_id      = db.Column(db.Integer, db.ForeignKey('kpi_sections.id', ondelete='CASCADE'), nullable=False)
    # SQL Server لا يسمح بمسارات CASCADE متعددة للجدول نفسه
    # الحذف يصل عبر kpi_sections → kpi_criteria تلقائياً
    template_id     = db.Column(db.Integer, db.ForeignKey('kpi_templates.id'), nullable=False)
    name            = db.Column(db.String(250), nullable=False)
    max_score       = db.Column(db.Numeric(5, 2), nullable=False, default=10)
    sort_order      = db.Column(db.Integer, default=0)

    # إعداد تكرار التقييم
    # daily         = كل يوم عمل
    # every_n_days  = كل N أيام (frequency_value = N)
    # weekly        = مرة أسبوعياً (frequency_value = رقم اليوم 0=أحد...6=سبت)
    # biweekly      = كل أسبوعين
    # monthly       = مرة شهرياً (frequency_value = رقم اليوم في الشهر أو null = آخر يوم)
    frequency_type  = db.Column(
        db.String(20),
        nullable=False,
        default='daily'
    )
    frequency_value = db.Column(db.Integer, nullable=True)  # قيمة مساعدة حسب نوع التكرار
    carry_over      = db.Column(db.Boolean, default=False)   # هل ينتقل للغياب؟

    created_at      = db.Column(db.DateTime, default=datetime.now)
    updated_at      = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    scores          = db.relationship('KpiCriterionScore', backref='criterion', lazy='dynamic')

    def __repr__(self):
        return f'<KpiCriterion {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'section_id': self.section_id,
            'template_id': self.template_id,
            'name': self.name,
            'max_score': float(self.max_score),
            'sort_order': self.sort_order,
            'frequency_type': self.frequency_type,
            'frequency_value': self.frequency_value,
            'carry_over': self.carry_over,
        }


class KpiEmployeeAssignment(db.Model):
    """
    ربط موظف بقالب KPI مع تاريخ البداية والنهاية.
    موظف واحد يمكن ربطه بقالب واحد نشط في نفس الوقت.
    """
    __tablename__ = 'kpi_employee_assignments'

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('kpi_templates.id'), nullable=False)
    assigned_by = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    start_date  = db.Column(db.Date, nullable=False)
    end_date    = db.Column(db.Date, nullable=True)   # null = نشط حتى الآن
    is_active   = db.Column(db.Boolean, default=True)
    created_at  = db.Column(db.DateTime, default=datetime.now)
    updated_at  = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    employee    = db.relationship('Employee', foreign_keys=[employee_id], backref=db.backref('kpi_assignments', lazy='dynamic'))
    assigner    = db.relationship('Employee', foreign_keys=[assigned_by])

    __table_args__ = (
        db.UniqueConstraint('employee_id', 'template_id', 'start_date', name='uq_kpi_assignment'),
    )

    def __repr__(self):
        return f'<KpiAssignment emp={self.employee_id} tpl={self.template_id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'employee_name': self.employee.full_name if self.employee else None,
            'template_id': self.template_id,
            'template_name': self.template.name if self.template else None,
            'assigned_by': self.assigned_by,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class KpiDailyEvaluation(db.Model):
    """
    تقييم يومي لموظف.
    يُحسب فقط لأيام الحضور الفعلي (status='present' في جدول الحضور).
    لا يُسمح بإدخال تقييم ليوم غياب أو إجازة.
    """
    __tablename__ = 'kpi_daily_evaluations'

    id                 = db.Column(db.Integer, primary_key=True, autoincrement=True)
    employee_id        = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    template_id        = db.Column(db.Integer, db.ForeignKey('kpi_templates.id'), nullable=False)
    evaluation_date    = db.Column(db.Date, nullable=False)
    evaluated_by       = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    # مجموع درجات جميع المعايير المستحقة في هذا اليوم
    total_score        = db.Column(db.Numeric(7, 2), default=0)
    # مجموع الدرجات القصوى للمعايير المستحقة فقط في هذا اليوم
    max_possible_score = db.Column(db.Numeric(7, 2), default=0)
    # النسبة اليومية = (total_score / max_possible_score) * 100
    daily_percentage   = db.Column(db.Numeric(5, 2), default=0)
    notes              = db.Column(db.Text, nullable=True)
    status             = db.Column(db.String(20), default='submitted')  # draft / submitted / approved
    created_at         = db.Column(db.DateTime, default=datetime.now)
    updated_at         = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    employee    = db.relationship('Employee', foreign_keys=[employee_id], backref=db.backref('kpi_evaluations', lazy='dynamic'))
    evaluator   = db.relationship('Employee', foreign_keys=[evaluated_by])
    template    = db.relationship('KpiTemplate', backref=db.backref('daily_evaluations', lazy='dynamic'))
    scores      = db.relationship('KpiCriterionScore', backref='daily_evaluation', lazy='dynamic',
                                  cascade='all, delete-orphan')

    __table_args__ = (
        # موظف واحد = تقييم واحد في اليوم
        db.UniqueConstraint('employee_id', 'evaluation_date', name='uq_daily_eval'),
    )

    def __repr__(self):
        return f'<KpiDailyEvaluation emp={self.employee_id} date={self.evaluation_date}>'

    def to_dict(self, include_scores=False):
        data = {
            'id': self.id,
            'employee_id': self.employee_id,
            'employee_name': self.employee.full_name if self.employee else None,
            'template_id': self.template_id,
            'evaluation_date': self.evaluation_date.isoformat() if self.evaluation_date else None,
            'evaluated_by': self.evaluated_by,
            'total_score': float(self.total_score) if self.total_score else 0,
            'max_possible_score': float(self.max_possible_score) if self.max_possible_score else 0,
            'daily_percentage': float(self.daily_percentage) if self.daily_percentage else 0,
            'notes': self.notes,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        if include_scores:
            data['scores'] = [s.to_dict() for s in self.scores.all()]
        return data


class KpiCriterionScore(db.Model):
    """
    درجة معيار واحد داخل تقييم يومي.
    يحتفظ بنسخة من الدرجة القصوى وقت الإدخال.
    """
    __tablename__ = 'kpi_criterion_scores'

    id                   = db.Column(db.Integer, primary_key=True, autoincrement=True)
    daily_evaluation_id  = db.Column(db.Integer, db.ForeignKey('kpi_daily_evaluations.id', ondelete='CASCADE'), nullable=False)
    criterion_id         = db.Column(db.Integer, db.ForeignKey('kpi_criteria.id'), nullable=False)
    score                = db.Column(db.Numeric(5, 2), nullable=False)
    max_score            = db.Column(db.Numeric(5, 2), nullable=False)  # نسخة وقت الإدخال
    notes                = db.Column(db.Text, nullable=True)
    created_at           = db.Column(db.DateTime, default=datetime.now)
    updated_at           = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        db.UniqueConstraint('daily_evaluation_id', 'criterion_id', name='uq_criterion_score'),
    )

    def __repr__(self):
        return f'<KpiCriterionScore eval={self.daily_evaluation_id} crit={self.criterion_id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'daily_evaluation_id': self.daily_evaluation_id,
            'criterion_id': self.criterion_id,
            'criterion_name': self.criterion.name if self.criterion else None,
            'score': float(self.score),
            'max_score': float(self.max_score),
            'notes': self.notes,
        }


class KpiMonthlySummary(db.Model):
    """
    ملخص شهري لأداء موظف — محسوب ومخزّن مسبقاً للأداء.
    يُعاد حسابه عند:
      - إضافة/تعديل تقييم يومي
      - تعديل سجل حضور
      - نهاية الشهر (cron)
      - طلب يدوي من المدير

    القاعدة الأساسية:
      monthly_percentage = Σ(total_score للأيام المقيّمة)
                           ÷ Σ(max_possible_score لنفس الأيام) × 100
      لا تُحتسب أيام الغياب/الإجازة في البسط أو المقام.
    """
    __tablename__ = 'kpi_monthly_summaries'

    id                  = db.Column(db.Integer, primary_key=True, autoincrement=True)
    employee_id         = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    template_id         = db.Column(db.Integer, db.ForeignKey('kpi_templates.id'), nullable=False)
    year                = db.Column(db.Integer, nullable=False)
    month               = db.Column(db.Integer, nullable=False)   # 1–12
    # عدد أيام الحضور الفعلي من جدول البصمة
    total_attended_days = db.Column(db.Integer, default=0)
    # عدد أيام الحضور التي يجب أن يكون لها تقييم
    total_evaluable_days = db.Column(db.Integer, default=0)
    # عدد الأيام التي تم تقييمها فعلاً
    evaluated_days      = db.Column(db.Integer, default=0)
    total_score         = db.Column(db.Numeric(9, 2), default=0)
    max_possible_score  = db.Column(db.Numeric(9, 2), default=0)
    # النسبة الشهرية = (total_score / max_possible_score) * 100
    monthly_percentage  = db.Column(db.Numeric(5, 2), default=0)
    # التقييم: excellent / good / average / poor / not_evaluated
    performance_grade   = db.Column(db.String(20), default='not_evaluated')
    manager_comment     = db.Column(db.Text, nullable=True)
    is_finalized        = db.Column(db.Boolean, default=False)
    computed_at         = db.Column(db.DateTime, nullable=True)
    created_at          = db.Column(db.DateTime, default=datetime.now)
    updated_at          = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    employee    = db.relationship('Employee', backref=db.backref('kpi_monthly_summaries', lazy='dynamic'))
    template    = db.relationship('KpiTemplate', backref=db.backref('monthly_summaries', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('employee_id', 'year', 'month', name='uq_monthly_summary'),
    )

    def __repr__(self):
        return f'<KpiMonthlySummary emp={self.employee_id} {self.year}-{self.month:02d}>'

    def to_dict(self):
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'employee_name': self.employee.full_name if self.employee else None,
            'template_id': self.template_id,
            'template_name': self.template.name if self.template else None,
            'year': self.year,
            'month': self.month,
            'total_attended_days': self.total_attended_days,
            'total_evaluable_days': self.total_evaluable_days,
            'evaluated_days': self.evaluated_days,
            'total_score': float(self.total_score) if self.total_score else 0,
            'max_possible_score': float(self.max_possible_score) if self.max_possible_score else 0,
            'monthly_percentage': float(self.monthly_percentage) if self.monthly_percentage else 0,
            'performance_grade': self.performance_grade,
            'manager_comment': self.manager_comment,
            'is_finalized': self.is_finalized,
            'computed_at': self.computed_at.isoformat() if self.computed_at else None,
        }


class KpiSettings(db.Model):
    """
    إعدادات KPI العامة (صف واحد فقط في الجدول).
    عتبات التقييم قابلة للتخصيص.
    """
    __tablename__ = 'kpi_settings'

    id                  = db.Column(db.Integer, primary_key=True, default=1)
    excellent_threshold = db.Column(db.Numeric(5, 2), default=95.00)
    good_threshold      = db.Column(db.Numeric(5, 2), default=80.00)
    average_threshold   = db.Column(db.Numeric(5, 2), default=60.00)
    default_max_score   = db.Column(db.Numeric(5, 2), default=10.00)
    allow_self_view     = db.Column(db.Boolean, default=True)
    updated_by          = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    updated_at          = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'excellent_threshold': float(self.excellent_threshold),
            'good_threshold': float(self.good_threshold),
            'average_threshold': float(self.average_threshold),
            'default_max_score': float(self.default_max_score),
            'allow_self_view': self.allow_self_view,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def get(cls):
        """جلب الإعدادات (أو إنشاؤها إن لم تكن موجودة)."""
        s = cls.query.first()
        if not s:
            s = cls(id=1)
            db.session.add(s)
            db.session.commit()
        return s

    def get_grade(self, percentage):
        """
        تحديد التقييم النوعي بناءً على النسبة المئوية.
        يستخدم العتبات المخزّنة في هذا الصف.
        """
        if percentage is None:
            return 'not_evaluated'
        pct = float(percentage)
        if pct >= float(self.excellent_threshold):
            return 'excellent'
        elif pct >= float(self.good_threshold):
            return 'good'
        elif pct >= float(self.average_threshold):
            return 'average'
        else:
            return 'poor'
