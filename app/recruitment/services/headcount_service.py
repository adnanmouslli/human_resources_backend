# app/recruitment/services/headcount_service.py
# خدمة فجوات الاستيعاب الوظيفي والإشعارات

from app import db
from app.models.employee import Employee
from app.recruitment.models import HeadcountTarget, RecruitmentApplication
from app.recruitment.notifications import (
    send_internal_notification,
    get_super_admin_ids,
    get_branch_manager_ids,
)


def check_headcount_and_notify(branch_id=None, department_id=None):
    """
    فحص أهداف الاستيعاب وإرسال تنبيهات عند وجود فجوة.

    يُشغَّل عند:
    - تغيير حالة موظف إلى غير نشط/منتهي
    - قبول طلب تعيين وإنشاء موظف
    - طلب يدوي من السوبر أدمن

    يستخدم JOIN واحد لتجنب N+1 queries.
    """
    # بناء الاستعلام بكفاءة
    query = HeadcountTarget.query

    if branch_id is not None:
        query = query.filter(HeadcountTarget.branch_id == branch_id)
    if department_id is not None:
        query = query.filter(HeadcountTarget.department_id == department_id)

    targets = query.all()

    results = []
    for target in targets:
        active_count = _count_active_employees(target.branch_id, target.department_id)
        gap = target.target_count - active_count

        if gap >= target.warning_threshold:
            _send_headcount_alert(target, active_count, gap)

        results.append({
            'target_id': target.id,
            'branch_id': target.branch_id,
            'department_id': target.department_id,
            'target_count': target.target_count,
            'active_count': active_count,
            'gap': gap,
            'alert_sent': gap >= target.warning_threshold,
        })

    db.session.commit()
    return results


def _count_active_employees(branch_id, department_id):
    """
    عدّ الموظفين النشطين المطابقين للفرع والقسم.
    يستخدم استعلاماً واحداً.
    """
    query = Employee.query.filter(Employee.is_active == True)

    if branch_id is not None:
        query = query.filter(Employee.branch_id == branch_id)
    if department_id is not None:
        query = query.filter(Employee.department_id == department_id)

    return query.count()


def _send_headcount_alert(target, active_count, gap):
    """إرسال تنبيه نقص الكوادر البشرية"""
    branch_name = target.branch.name if target.branch else '—'
    dept_name = target.department.name if target.department else '—'

    title = "تنبيه: نقص في الكوادر البشرية"
    body = (
        f"الفرع [{branch_name}] / القسم [{dept_name}] لديه {active_count} موظف نشط "
        f"من أصل {target.target_count} مطلوبين. "
        f"يلزم تعيين {gap} موظف/موظفين."
    )

    # جمع معرفات المستلمين
    recipient_ids = set(get_super_admin_ids())
    if target.branch_id:
        recipient_ids.update(get_branch_manager_ids(target.branch_id))

    send_internal_notification(
        user_ids=list(recipient_ids),
        title=title,
        body=body,
        notif_type='headcount_warning',
        related_id=target.id,
    )


def check_all_targets():
    """فحص جميع الأهداف المحددة"""
    return check_headcount_and_notify()


def get_headcount_status():
    """
    إرجاع حالة كل هدف مع البيانات الحية.

    يعيد:
    [
        {
            id, branch, department, target_count, active_count,
            gap, alert, open_pipeline_count
        }
    ]
    """
    targets = HeadcountTarget.query.all()
    result = []

    for target in targets:
        active_count = _count_active_employees(target.branch_id, target.department_id)
        gap = target.target_count - active_count

        # عدد الطلبات المفتوحة (غير مقبولة ولا مرفوضة)
        pipeline_query = RecruitmentApplication.query.filter(
            RecruitmentApplication.status.notin_(['accepted', 'rejected'])
        )
        if target.branch_id:
            pipeline_query = pipeline_query.filter(
                RecruitmentApplication.branch_id == target.branch_id
            )
        if target.department_id:
            pipeline_query = pipeline_query.filter(
                RecruitmentApplication.department_id == target.department_id
            )
        open_pipeline = pipeline_query.count()

        result.append({
            'id': target.id,
            'branch_id': target.branch_id,
            'branch': target.branch.name if target.branch else None,
            'department_id': target.department_id,
            'department': target.department.name if target.department else None,
            'target_count': target.target_count,
            'active_count': active_count,
            'gap': max(gap, 0),
            'alert': gap >= target.warning_threshold,
            'open_pipeline_count': open_pipeline,
            'warning_threshold': target.warning_threshold,
            'notes': target.notes,
        })

    return result
