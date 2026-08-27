# app/recruitment/services/status_service.py
# خدمة إدارة حالات الطلبات وقرارات التعيين

from datetime import datetime, date
from app import db
from app.recruitment.models import (
    RecruitmentApplication,
    HiringDecision,
    ALLOWED_STATUSES,
)
from app.recruitment.notifications import (
    send_internal_notification,
    get_super_admin_ids,
)
from app.recruitment.services.employee_mapper import create_employee_from_application
from app.recruitment.services.headcount_service import check_headcount_and_notify


# ─────────────────────────────────────────────────────────────────
# قواعد الانتقال بين الحالات
# ─────────────────────────────────────────────────────────────────

VALID_TRANSITIONS = {
    'new':          ['under_review', 'accepted', 'rejected'],
    'under_review': ['interview', 'accepted', 'rejected'],
    'interview':    ['accepted', 'rejected'],
    'accepted':     [],   # حالة نهائية
    'rejected':     [],   # حالة نهائية
}


def is_valid_transition(current_status, new_status):
    allowed = VALID_TRANSITIONS.get(current_status, [])
    return new_status in allowed


# ─────────────────────────────────────────────────────────────────
# تحديث الحالة
# ─────────────────────────────────────────────────────────────────

def update_application_status(application_id, new_status, extra_data=None, acting_user_id=None):
    """
    تحديث حالة طلب التوظيف مع تطبيق قواعد الانتقال.

    يعيد (application, error_message).

    extra_data يمكن أن يحتوي على:
        - rejection_reason (مطلوب عند الرفض)
        - evaluation_score (اختياري)
    """
    if extra_data is None:
        extra_data = {}

    application = RecruitmentApplication.query.get(application_id)
    if not application:
        return None, "الطلب غير موجود"

    if new_status not in ALLOWED_STATUSES:
        return None, f"الحالة '{new_status}' غير مسموح بها"

    if not is_valid_transition(application.status, new_status):
        return None, (
            f"لا يمكن الانتقال من '{application.status}' إلى '{new_status}'. "
            f"الانتقالات المسموحة: {VALID_TRANSITIONS.get(application.status, [])}"
        )

    # التحقق من البيانات المطلوبة حسب الحالة
    if new_status == 'rejected':
        if not extra_data.get('rejection_reason'):
            return None, "سبب الرفض مطلوب عند رفض الطلب"
        application.rejection_reason = extra_data['rejection_reason']

    # تحديث الحالة
    old_status = application.status
    application.status = new_status
    application.updated_at = datetime.now()

    if 'evaluation_score' in extra_data:
        application.evaluation_score = extra_data['evaluation_score']

    db.session.commit()

    # إرسال الإشعارات بعد الـ commit
    _send_status_notifications(application, old_status, new_status)

    return application, None


# ─────────────────────────────────────────────────────────────────
# قرار التعيين (القبول)
# ─────────────────────────────────────────────────────────────────

def process_hire(application_id, hiring_data, acting_user_id):
    """
    معالجة قرار التعيين:
    1. التحقق من الانتقال إلى 'accepted'
    2. التحقق من صحة البيانات (الفرع، القسم، المسمى، البصمة، الوردية، المهنة)
    3. إنشاء سجل HiringDecision
    4. إنشاء الموظف تلقائياً بكل البيانات
    5. فحص الاستيعاب وإرسال التنبيهات
    6. تحديث الحالة

    يعيد:
    {
        application: { ... },
        hiring_decision: { ... },
        employee_id: int | None,
        warning: str | None
    }
    أو يعيد (None, error_message)
    """
    from app.models.branch import Branch
    from app.models.department import Department, BranchDepartment
    from app.models.job_title import JobTitle
    from app.models.shift import Shift
    from app.models.profession import Profession
    from app.models.employee import Employee

    application = RecruitmentApplication.query.get(application_id)
    if not application:
        return None, "الطلب غير موجود"

    if not is_valid_transition(application.status, 'accepted'):
        return None, (
            f"لا يمكن قبول الطلب من الحالة '{application.status}'. "
            "يجب أن يكون الطلب في مرحلة المقابلة."
        )

    # التحقق من عدم وجود قرار تعيين سابق
    if application.hiring_decision:
        return None, "يوجد قرار تعيين مسبق لهذا الطلب"

    # ──── التحقق من الحقول المطلوبة ────
    # ملاحظة: salary, start_date, fingerprint_id أصبحت اختيارية
    required = ['branch_id', 'department_id', 'job_title_id',
                'employee_type', 'work_system']
    missing = [f for f in required if not hiring_data.get(f)]
    if missing:
        labels = {
            'branch_id': 'الفرع', 'department_id': 'القسم',
            'job_title_id': 'المسمى الوظيفي',
            'employee_type': 'نوع الموظف',
            'work_system': 'نظام العمل',
        }
        missing_labels = [labels.get(f, f) for f in missing]
        return None, f"الحقول المطلوبة مفقودة: {', '.join(missing_labels)}"

    # تحويل start_date إذا كانت نصاً (اختيارية الآن)
    start_date = hiring_data.get('start_date')
    if start_date:
        if isinstance(start_date, str):
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            except ValueError:
                return None, "تاريخ البداية غير صالح (يجب YYYY-MM-DD)"
    else:
        start_date = None

    # التحقق من نوع الموظف
    employee_type = hiring_data['employee_type']
    if employee_type not in ('permanent', 'temporary'):
        return None, "نوع الموظف يجب أن يكون 'permanent' أو 'temporary'"

    # ──── التحقق من صحة الـ FKs ────

    # الفرع
    branch = Branch.query.get(hiring_data['branch_id'])
    if not branch:
        return None, "الفرع غير موجود"

    # القسم
    department = Department.query.get(hiring_data['department_id'])
    if not department:
        return None, "القسم غير موجود"

    # التحقق من أن القسم تابع للفرع
    branch_dept = BranchDepartment.query.filter_by(
        branch_id=hiring_data['branch_id'],
        department_id=hiring_data['department_id']
    ).first()
    if not branch_dept:
        return None, "القسم غير متوفر في الفرع المحدد"

    # المسمى الوظيفي
    job_title = JobTitle.query.get(hiring_data['job_title_id'])
    if not job_title:
        return None, "المسمى الوظيفي غير موجود"

    # التحقق من البصمة الفريدة (اختيارية الآن)
    raw_fp = hiring_data.get('fingerprint_id')
    fingerprint_id = str(raw_fp).strip() if raw_fp is not None and str(raw_fp).strip() != '' else None
    if fingerprint_id:
        existing_fp = Employee.query.filter_by(fingerprint_id=fingerprint_id).first()
        if existing_fp:
            return None, f"رقم البصمة '{fingerprint_id}' مستخدم مسبقاً للموظف: {existing_fp.full_name}"

    # الوردية (إذا كان نظام ورديات)
    shift_id = None
    if job_title.shift_system and hiring_data.get('shift_id'):
        shift = Shift.query.get(hiring_data['shift_id'])
        if not shift:
            return None, "الوردية غير موجودة"
        shift_id = shift.id

    # المهنة (للمؤقتين فقط)
    profession_id = None
    if employee_type == 'temporary':
        if not hiring_data.get('profession_id'):
            return None, "المهنة مطلوبة للموظف المؤقت"
        profession = Profession.query.get(hiring_data['profession_id'])
        if not profession:
            return None, "المهنة غير موجودة"
        profession_id = profession.id

    # ──── إنشاء قرار التعيين ────
    hiring_decision = HiringDecision(
        application_id=application_id,
        branch_id=hiring_data['branch_id'],
        department_id=hiring_data['department_id'],
        job_title_id=hiring_data['job_title_id'],
        salary=hiring_data.get('salary'),
        start_date=start_date,
        employee_type=employee_type,
        work_system=hiring_data['work_system'],
        shift_id=shift_id,
        profession_id=profession_id,
        fingerprint_id=fingerprint_id,
        probation_salary=hiring_data.get('probation_salary'),
        working_hours=hiring_data.get('working_hours'),
        notes=hiring_data.get('notes'),
        decided_by=acting_user_id,
    )
    db.session.add(hiring_decision)
    db.session.flush()

    # ──── إنشاء الموظف تلقائياً ────
    employee_result, emp_error = create_employee_from_application(
        application_id,
        {
            'fingerprint_id': fingerprint_id,
            'salary': hiring_data.get('salary'),
            'start_date': start_date,
            'branch_id': hiring_data['branch_id'],
            'department_id': hiring_data['department_id'],
            'job_title_id': hiring_data['job_title_id'],
            'employee_type': employee_type,
            'work_system': hiring_data['work_system'],
            'shift_id': shift_id,
            'profession_id': profession_id,
        }
    )

    employee_id = None
    warning = None

    if emp_error:
        warning = f"تعذر إنشاء الموظف: {emp_error}"
    elif employee_result:
        employee_id = employee_result['employee_id']
        warning = employee_result.get('warning')
        hiring_decision.employee_id = employee_id

    # تحديث حالة الطلب
    application.status = 'accepted'
    application.updated_at = datetime.now()

    db.session.commit()

    # فحص الاستيعاب بعد الـ commit
    check_headcount_and_notify(
        branch_id=hiring_decision.branch_id,
        department_id=hiring_decision.department_id
    )

    # إشعار منشئ الطلب والسوبر أدمن
    _notify_acceptance(application, acting_user_id)

    return {
        'application': application.to_dict(),
        'hiring_decision': hiring_decision.to_dict(),
        'employee_id': employee_id,
        'warning': warning,
    }, None


# ─────────────────────────────────────────────────────────────────
# إشعارات الحالة
# ─────────────────────────────────────────────────────────────────

def _send_status_notifications(application, old_status, new_status):
    """إرسال إشعارات عند تغيير الحالة"""
    creator_id = application.created_by
    super_admin_ids = get_super_admin_ids()

    if new_status == 'rejected':
        recipient_ids = list(set([creator_id] + super_admin_ids))
        send_internal_notification(
            user_ids=recipient_ids,
            title="تم رفض طلب التوظيف",
            body=(
                f"تم رفض طلب التوظيف رقم {application.id} "
                f"للوظيفة: {application.applied_position}. "
                f"السبب: {application.rejection_reason}"
            ),
            notif_type='recruitment',
            related_id=application.id,
        )
        db.session.commit()

    elif new_status == 'under_review':
        send_internal_notification(
            user_ids=super_admin_ids,
            title="طلب توظيف قيد المراجعة",
            body=f"الطلب رقم {application.id} للوظيفة '{application.applied_position}' قيد المراجعة.",
            notif_type='recruitment',
            related_id=application.id,
        )
        db.session.commit()

    elif new_status == 'interview':
        send_internal_notification(
            user_ids=[creator_id] + super_admin_ids,
            title="دعوة مقابلة",
            body=f"الطلب رقم {application.id} للوظيفة '{application.applied_position}' وصل لمرحلة المقابلة.",
            notif_type='recruitment',
            related_id=application.id,
        )
        db.session.commit()


def _notify_acceptance(application, acting_user_id):
    """إشعار القبول"""
    creator_id = application.created_by
    super_admin_ids = get_super_admin_ids()
    recipient_ids = list(set([creator_id] + super_admin_ids))

    send_internal_notification(
        user_ids=recipient_ids,
        title="تم قبول المتقدم وتعيينه",
        body=(
            f"تم قبول الطلب رقم {application.id} "
            f"للوظيفة '{application.applied_position}' وتحويل المتقدم إلى موظف."
        ),
        notif_type='recruitment',
        related_id=application.id,
    )
    db.session.commit()
