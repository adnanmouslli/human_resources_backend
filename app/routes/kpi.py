# app/routes/kpi.py
# نقاط نهاية API لموديول KPI - تقييم الأداء الوظيفي

from datetime import date, datetime
from flask import Blueprint, request, jsonify
from sqlalchemy import extract

from app import db
from app.utils import token_required
from app.models.kpi import (
    KpiTemplate, KpiSection, KpiCriterion,
    KpiEmployeeAssignment, KpiDailyEvaluation, KpiCriterionScore,
    KpiMonthlySummary, KpiSettings,
)
from app.models.employee import Employee
from app.models.attendance import Attendance
from app.services.kpi_frequency_service import KpiFrequencyService
from app.services.kpi_scoring_service import KpiScoringService

kpi_bp = Blueprint('kpi', __name__)

# ─────────────────────────────────────────────────────────────────────
# مساعدات داخلية
# ─────────────────────────────────────────────────────────────────────

def _admin_or_manager(user):
    """هل المستخدم مدير أو مشرف؟"""
    return user.user_type in ('super_admin', 'branch_head', 'department_head',
                               'branch_deputy', 'department_deputy')

def _is_admin(user):
    return user.user_type == 'super_admin'

def _get_accessible_employee_ids(user) -> list:
    """
    يُعيد قائمة بمعرّفات الموظفين الذين يحق للمستخدم رؤيتهم.
    - super_admin   → جميع الموظفين
    - branch_head / branch_deputy   → موظفو فروعه فقط
    - department_head / department_deputy → موظفو أقسامه فقط
    - employee (موظف عادي) → نفسه فقط
    يعتمد على get_accessible_employees() الموجودة في نموذج User.
    """
    employees = user.get_accessible_employees()
    return [e.id for e in employees] if employees else []

def _can_access_employee(user, employee_id: int) -> bool:
    """
    هل يملك المستخدم صلاحية الوصول لبيانات موظف معين؟
    """
    if _is_admin(user):
        return True
    return employee_id in _get_accessible_employee_ids(user)

def _parse_date(s):
    """تحويل نص إلى date."""
    if not s:
        return None
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except ValueError:
        return None

def _check_attendance_present(employee_id: int, eval_date: date):
    """
    التحقق من أن الموظف كان حاضراً في التاريخ المحدد.
    يُعيد None إذا كان حاضراً، وإلا يُعيد رسالة خطأ.
    """
    att = Attendance.query.filter(
        Attendance.empId == employee_id,
        Attendance.createdAt == eval_date,
        Attendance.checkInTime != None,
    ).first()
    if not att:
        return "هذا اليوم غير مسجّل كحضور في النظام. لا يمكن إدخال تقييم لأيام الغياب."
    return None


# ═══════════════════════════════════════════════════════════════════════
# SECTION A — إدارة القوالب (Templates)
# ═══════════════════════════════════════════════════════════════════════

@kpi_bp.route('/api/kpi/templates', methods=['GET'])
@token_required
def list_templates(user):
    """قائمة جميع قوالب KPI."""
    templates = KpiTemplate.query.order_by(KpiTemplate.created_at.desc()).all()
    return jsonify([t.to_dict() for t in templates]), 200


@kpi_bp.route('/api/kpi/templates', methods=['POST'])
@token_required
def create_template(user):
    """إنشاء قالب KPI جديد."""
    if not _admin_or_manager(user):
        return jsonify({'message': 'غير مصرح لك بإنشاء القوالب'}), 403

    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'message': 'اسم القالب مطلوب'}), 400

    tpl = KpiTemplate(
        name=name,
        description=data.get('description'),
        job_title_id=data.get('job_title_id'),
        is_active=data.get('is_active', True),
        created_by=user.employee_id,
    )
    db.session.add(tpl)
    db.session.commit()

    # إضافة الأقسام والمعايير إن أُرسلت
    sections_data = data.get('sections', [])
    for s_idx, sec in enumerate(sections_data):
        section = KpiSection(
            template_id=tpl.id,
            name=sec.get('name', f'قسم {s_idx+1}'),
            sort_order=sec.get('sort_order', s_idx),
        )
        db.session.add(section)
        db.session.flush()
        for c_idx, crit in enumerate(sec.get('criteria', [])):
            criterion = KpiCriterion(
                section_id=section.id,
                template_id=tpl.id,
                name=crit.get('name', ''),
                max_score=crit.get('max_score', 10),
                sort_order=crit.get('sort_order', c_idx),
                frequency_type=crit.get('frequency_type', 'daily'),
                frequency_value=crit.get('frequency_value'),
                carry_over=crit.get('carry_over', False),
            )
            db.session.add(criterion)

    db.session.commit()
    return jsonify(tpl.to_dict(include_sections=True)), 201


@kpi_bp.route('/api/kpi/templates/<int:tpl_id>', methods=['GET'])
@token_required
def get_template(user, tpl_id):
    """جلب قالب واحد مع أقسامه ومعاييره."""
    tpl = KpiTemplate.query.get_or_404(tpl_id)
    return jsonify(tpl.to_dict(include_sections=True)), 200


@kpi_bp.route('/api/kpi/templates/<int:tpl_id>', methods=['PUT'])
@token_required
def update_template(user, tpl_id):
    """تحديث قالب KPI."""
    if not _admin_or_manager(user):
        return jsonify({'message': 'غير مصرح لك بتعديل القوالب'}), 403

    tpl = KpiTemplate.query.get_or_404(tpl_id)
    data = request.get_json() or {}

    tpl.name        = data.get('name', tpl.name).strip()
    tpl.description = data.get('description', tpl.description)
    tpl.job_title_id = data.get('job_title_id', tpl.job_title_id)
    tpl.is_active   = data.get('is_active', tpl.is_active)
    db.session.commit()
    return jsonify(tpl.to_dict()), 200


@kpi_bp.route('/api/kpi/templates/<int:tpl_id>', methods=['DELETE'])
@token_required
def delete_template(user, tpl_id):
    """حذف ناعم للقالب (soft delete)."""
    if not _is_admin(user):
        return jsonify({'message': 'يُسمح للمدير العام فقط بحذف القوالب'}), 403

    tpl = KpiTemplate.query.get_or_404(tpl_id)
    tpl.is_active = False
    db.session.commit()
    return jsonify({'message': 'تم إلغاء تفعيل القالب بنجاح'}), 200


@kpi_bp.route('/api/kpi/templates/<int:tpl_id>/duplicate', methods=['POST'])
@token_required
def duplicate_template(user, tpl_id):
    """نسخ قالب KPI."""
    if not _admin_or_manager(user):
        return jsonify({'message': 'غير مصرح لك'}), 403

    src = KpiTemplate.query.get_or_404(tpl_id)
    new_tpl = KpiTemplate(
        name=f'{src.name} - نسخة',
        description=src.description,
        job_title_id=src.job_title_id,
        is_active=True,
        created_by=user.employee_id,
    )
    db.session.add(new_tpl)
    db.session.flush()

    for sec in src.sections.order_by(KpiSection.sort_order).all():
        new_sec = KpiSection(
            template_id=new_tpl.id,
            name=sec.name,
            sort_order=sec.sort_order,
        )
        db.session.add(new_sec)
        db.session.flush()
        for crit in sec.criteria.order_by(KpiCriterion.sort_order).all():
            new_crit = KpiCriterion(
                section_id=new_sec.id,
                template_id=new_tpl.id,
                name=crit.name,
                max_score=crit.max_score,
                sort_order=crit.sort_order,
                frequency_type=crit.frequency_type,
                frequency_value=crit.frequency_value,
                carry_over=crit.carry_over,
            )
            db.session.add(new_crit)

    db.session.commit()
    return jsonify(new_tpl.to_dict(include_sections=True)), 201


# ═══════════════════════════════════════════════════════════════════════
# SECTION B — الأقسام والمعايير
# ═══════════════════════════════════════════════════════════════════════

@kpi_bp.route('/api/kpi/templates/<int:tpl_id>/sections', methods=['POST'])
@token_required
def add_section(user, tpl_id):
    """إضافة قسم جديد لقالب."""
    if not _admin_or_manager(user):
        return jsonify({'message': 'غير مصرح لك'}), 403

    KpiTemplate.query.get_or_404(tpl_id)
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'message': 'اسم القسم مطلوب'}), 400

    sec = KpiSection(
        template_id=tpl_id,
        name=name,
        sort_order=data.get('sort_order', 0),
    )
    db.session.add(sec)
    db.session.commit()
    return jsonify(sec.to_dict()), 201


@kpi_bp.route('/api/kpi/sections/<int:sec_id>', methods=['PUT'])
@token_required
def update_section(user, sec_id):
    if not _admin_or_manager(user):
        return jsonify({'message': 'غير مصرح لك'}), 403

    sec = KpiSection.query.get_or_404(sec_id)
    data = request.get_json() or {}
    sec.name       = data.get('name', sec.name).strip()
    sec.sort_order = data.get('sort_order', sec.sort_order)
    db.session.commit()
    return jsonify(sec.to_dict()), 200


@kpi_bp.route('/api/kpi/sections/<int:sec_id>', methods=['DELETE'])
@token_required
def delete_section(user, sec_id):
    if not _admin_or_manager(user):
        return jsonify({'message': 'غير مصرح لك'}), 403

    sec = KpiSection.query.get_or_404(sec_id)
    db.session.delete(sec)
    db.session.commit()
    return jsonify({'message': 'تم حذف القسم'}), 200


@kpi_bp.route('/api/kpi/sections/<int:sec_id>/criteria', methods=['POST'])
@token_required
def add_criterion(user, sec_id):
    """إضافة معيار جديد لقسم."""
    if not _admin_or_manager(user):
        return jsonify({'message': 'غير مصرح لك'}), 403

    sec = KpiSection.query.get_or_404(sec_id)
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'message': 'اسم المعيار مطلوب'}), 400

    freq_type = data.get('frequency_type', 'daily')
    valid_freq = ('daily', 'every_n_days', 'weekly', 'biweekly', 'monthly')
    if freq_type not in valid_freq:
        return jsonify({'message': f'نوع التكرار غير صحيح. الأنواع المقبولة: {", ".join(valid_freq)}'}), 400

    crit = KpiCriterion(
        section_id=sec.id,
        template_id=sec.template_id,
        name=name,
        max_score=data.get('max_score', 10),
        sort_order=data.get('sort_order', 0),
        frequency_type=freq_type,
        frequency_value=data.get('frequency_value'),
        carry_over=data.get('carry_over', False),
    )
    db.session.add(crit)
    db.session.commit()
    return jsonify(crit.to_dict()), 201


@kpi_bp.route('/api/kpi/criteria/<int:crit_id>', methods=['PUT'])
@token_required
def update_criterion(user, crit_id):
    if not _admin_or_manager(user):
        return jsonify({'message': 'غير مصرح لك'}), 403

    crit = KpiCriterion.query.get_or_404(crit_id)
    data = request.get_json() or {}
    crit.name            = data.get('name', crit.name).strip()
    crit.max_score       = data.get('max_score', crit.max_score)
    crit.sort_order      = data.get('sort_order', crit.sort_order)
    crit.frequency_type  = data.get('frequency_type', crit.frequency_type)
    crit.frequency_value = data.get('frequency_value', crit.frequency_value)
    crit.carry_over      = data.get('carry_over', crit.carry_over)
    db.session.commit()
    return jsonify(crit.to_dict()), 200


@kpi_bp.route('/api/kpi/criteria/<int:crit_id>', methods=['DELETE'])
@token_required
def delete_criterion(user, crit_id):
    if not _admin_or_manager(user):
        return jsonify({'message': 'غير مصرح لك'}), 403

    crit = KpiCriterion.query.get_or_404(crit_id)
    db.session.delete(crit)
    db.session.commit()
    return jsonify({'message': 'تم حذف المعيار'}), 200


@kpi_bp.route('/api/kpi/sections/<int:sec_id>/reorder', methods=['PUT'])
@token_required
def reorder_criteria(user, sec_id):
    """إعادة ترتيب المعايير بالسحب والإفلات."""
    if not _admin_or_manager(user):
        return jsonify({'message': 'غير مصرح لك'}), 403

    # body: { ordered_ids: [1, 5, 3, 2] }
    data = request.get_json() or {}
    ordered_ids = data.get('ordered_ids', [])
    for idx, crit_id in enumerate(ordered_ids):
        crit = KpiCriterion.query.get(crit_id)
        if crit and crit.section_id == sec_id:
            crit.sort_order = idx
    db.session.commit()
    return jsonify({'message': 'تم إعادة الترتيب'}), 200


# ═══════════════════════════════════════════════════════════════════════
# SECTION C — ربط الموظفين بالقوالب (Assignments)
# ═══════════════════════════════════════════════════════════════════════

@kpi_bp.route('/api/kpi/assignments', methods=['GET'])
@token_required
def list_assignments(user):
    """
    قائمة الربطات.
    - super_admin → يرى الكل
    - المديرون    → يرون فقط ربطات موظفيهم
    """
    accessible_ids = _get_accessible_employee_ids(user)
    assignments = KpiEmployeeAssignment.query.filter(
        KpiEmployeeAssignment.employee_id.in_(accessible_ids)
    ).order_by(KpiEmployeeAssignment.created_at.desc()).all()
    return jsonify([a.to_dict() for a in assignments]), 200


@kpi_bp.route('/api/kpi/assignments', methods=['POST'])
@token_required
def create_assignment(user):
    """ربط موظف بقالب KPI."""
    if not _admin_or_manager(user):
        return jsonify({'message': 'غير مصرح لك'}), 403

    data = request.get_json() or {}
    employee_id = data.get('employee_id')
    template_id = data.get('template_id')
    start_date  = _parse_date(data.get('start_date'))

    if not all([employee_id, template_id, start_date]):
        return jsonify({'message': 'employee_id و template_id و start_date مطلوبة'}), 400

    # التحقق أن الموظف ضمن نطاق صلاحية المستخدم
    if not _can_access_employee(user, employee_id):
        return jsonify({'message': 'ليس لديك صلاحية لربط هذا الموظف'}), 403

    # التحقق من عدم وجود ربط نشط آخر
    existing = KpiEmployeeAssignment.query.filter(
        KpiEmployeeAssignment.employee_id == employee_id,
        KpiEmployeeAssignment.is_active == True,
        db.or_(
            KpiEmployeeAssignment.end_date == None,
            KpiEmployeeAssignment.end_date >= start_date,
        )
    ).first()

    if existing:
        return jsonify({
            'message': 'الموظف لديه ربط نشط بالفعل. يرجى إنهاء الربط الحالي أولاً.',
            'existing_assignment': existing.to_dict(),
        }), 409

    assignment = KpiEmployeeAssignment(
        employee_id=employee_id,
        template_id=template_id,
        assigned_by=user.employee_id,
        start_date=start_date,
        end_date=_parse_date(data.get('end_date')),
        is_active=True,
    )
    db.session.add(assignment)
    db.session.commit()
    return jsonify(assignment.to_dict()), 201


@kpi_bp.route('/api/kpi/assignments/<int:asgn_id>', methods=['PUT'])
@token_required
def update_assignment(user, asgn_id):
    if not _admin_or_manager(user):
        return jsonify({'message': 'غير مصرح لك'}), 403

    asgn = KpiEmployeeAssignment.query.get_or_404(asgn_id)
    if not _can_access_employee(user, asgn.employee_id):
        return jsonify({'message': 'ليس لديك صلاحية لتعديل ربط هذا الموظف'}), 403
    data = request.get_json() or {}
    if 'template_id' in data:
        asgn.template_id = data['template_id']
    if 'end_date' in data:
        asgn.end_date = _parse_date(data['end_date'])
    if 'is_active' in data:
        asgn.is_active = data['is_active']
    db.session.commit()
    return jsonify(asgn.to_dict()), 200


@kpi_bp.route('/api/kpi/assignments/<int:asgn_id>', methods=['DELETE'])
@token_required
def deactivate_assignment(user, asgn_id):
    if not _admin_or_manager(user):
        return jsonify({'message': 'غير مصرح لك'}), 403

    asgn = KpiEmployeeAssignment.query.get_or_404(asgn_id)
    if not _can_access_employee(user, asgn.employee_id):
        return jsonify({'message': 'ليس لديك صلاحية لإلغاء ربط هذا الموظف'}), 403
    asgn.is_active = False
    asgn.end_date  = date.today()
    db.session.commit()
    return jsonify({'message': 'تم إلغاء الربط'}), 200


@kpi_bp.route('/api/kpi/employees/<int:emp_id>/active-template', methods=['GET'])
@token_required
def get_active_template(user, emp_id):
    """جلب القالب النشط الحالي لموظف."""
    if not _can_access_employee(user, emp_id):
        return jsonify({'message': 'ليس لديك صلاحية للوصول لبيانات هذا الموظف'}), 403

    check_date = _parse_date(request.args.get('date')) or date.today()
    asgn = KpiScoringService.get_active_assignment(emp_id, check_date)
    if not asgn:
        return jsonify({'message': 'لا يوجد قالب مرتبط بهذا الموظف'}), 404

    tpl = KpiTemplate.query.get(asgn.template_id)
    return jsonify({
        'assignment': asgn.to_dict(),
        'template': tpl.to_dict(include_sections=True) if tpl else None,
    }), 200


# ═══════════════════════════════════════════════════════════════════════
# SECTION D — التقييم اليومي (Daily Evaluation)
# ═══════════════════════════════════════════════════════════════════════

@kpi_bp.route('/api/kpi/evaluations/daily', methods=['GET'])
@token_required
def get_daily_evaluation(user):
    """
    جلب معايير التقييم المستحقة اليوم + الدرجات الموجودة + حالة الحضور.
    ?employee_id=X&date=YYYY-MM-DD
    """
    employee_id = request.args.get('employee_id', type=int)
    eval_date   = _parse_date(request.args.get('date'))

    if not employee_id or not eval_date:
        return jsonify({'message': 'employee_id و date مطلوبان'}), 400

    # التحقق من صلاحية الوصول للموظف
    if not _can_access_employee(user, employee_id):
        return jsonify({'message': 'ليس لديك صلاحية للوصول لبيانات هذا الموظف'}), 403

    # جلب الربط النشط
    asgn = KpiScoringService.get_active_assignment(employee_id, eval_date)
    if not asgn:
        return jsonify({'message': 'لا يوجد قالب KPI مرتبط بهذا الموظف في هذا التاريخ'}), 404

    tpl = KpiTemplate.query.get(asgn.template_id)

    # حالة الحضور
    att = Attendance.query.filter(
        Attendance.empId == employee_id,
        Attendance.createdAt == eval_date,
    ).first()

    if att and att.checkInTime:
        att_status = 'present'
    elif att:
        att_status = 'no_checkout'
    else:
        att_status = 'absent'

    # التقييم الموجود (إن وجد)
    existing_eval = KpiDailyEvaluation.query.filter_by(
        employee_id=employee_id,
        evaluation_date=eval_date,
    ).first()

    existing_scores = {}
    if existing_eval:
        for s in existing_eval.scores.all():
            existing_scores[s.criterion_id] = s.to_dict()

    # المعايير المستحقة اليوم
    all_criteria = KpiCriterion.query.filter_by(template_id=asgn.template_id).all()
    sections_out = []

    for sec in tpl.sections.order_by(KpiSection.sort_order).all():
        sec_criteria = [c for c in all_criteria if c.section_id == sec.id]
        criteria_out = []
        for crit in sorted(sec_criteria, key=lambda x: x.sort_order):
            is_due = KpiFrequencyService.is_due(crit, employee_id, eval_date, asgn.start_date)
            next_due = None
            if not is_due:
                nd = KpiFrequencyService.get_next_due_date(crit, employee_id, eval_date, asgn.start_date)
                next_due = nd.isoformat() if nd else None

            criteria_out.append({
                **crit.to_dict(),
                'is_due': is_due,
                'next_due_date': next_due,
                'existing_score': existing_scores.get(crit.id),
            })
        sections_out.append({
            **sec.to_dict(),
            'criteria': criteria_out,
        })

    return jsonify({
        'employee_id': employee_id,
        'date': eval_date.isoformat(),
        'attendance_status': att_status,
        'assignment': asgn.to_dict(),
        'existing_evaluation': existing_eval.to_dict(include_scores=True) if existing_eval else None,
        'sections': sections_out,
    }), 200


@kpi_bp.route('/api/kpi/evaluations/daily', methods=['POST'])
@token_required
def submit_daily_evaluation(user):
    """
    إرسال تقييم يومي.

    التحقق:
      1. الموظف كان حاضراً في هذا اليوم
      2. لا يوجد تقييم معتمد بالفعل
      3. كل درجة ≤ الدرجة القصوى للمعيار
      4. المعايير المرسلة مستحقة في هذا اليوم
    """
    if not _admin_or_manager(user):
        return jsonify({'message': 'غير مصرح لك بإدخال التقييمات'}), 403

    data = request.get_json() or {}
    employee_id = data.get('employee_id')
    eval_date   = _parse_date(data.get('date'))
    scores_data = data.get('scores', [])

    if not employee_id or not eval_date:
        return jsonify({'message': 'employee_id و date مطلوبان'}), 400

    # التحقق من صلاحية تقييم هذا الموظف
    if not _can_access_employee(user, employee_id):
        return jsonify({'message': 'ليس لديك صلاحية لتقييم هذا الموظف'}), 403

    # ── التحقق 1: الحضور ──────────────────────────────────────────
    err = _check_attendance_present(employee_id, eval_date)
    if err:
        return jsonify({'message': err}), 422

    # ── التحقق 2: لا يوجد تقييم معتمد ───────────────────────────
    existing = KpiDailyEvaluation.query.filter_by(
        employee_id=employee_id,
        evaluation_date=eval_date,
    ).first()
    if existing and existing.status == 'approved':
        return jsonify({'message': 'يوجد تقييم معتمد بالفعل لهذا اليوم ولا يمكن تعديله'}), 409

    # جلب الربط النشط
    asgn = KpiScoringService.get_active_assignment(employee_id, eval_date)
    if not asgn:
        return jsonify({'message': 'لا يوجد قالب KPI مرتبط بهذا الموظف'}), 404

    # ── التحقق 3 و4: الدرجات والمعايير المستحقة ──────────────────
    all_criteria = {c.id: c for c in KpiCriterion.query.filter_by(template_id=asgn.template_id).all()}
    due_criteria = {
        c.id: c for c in KpiFrequencyService.get_due_criteria(
            asgn.template_id, employee_id, eval_date, asgn.start_date
        )
    }

    valid_scores = []
    for s in scores_data:
        crit_id = s.get('criterion_id')
        score   = s.get('score')

        if crit_id not in all_criteria:
            continue  # معيار غير موجود في القالب → تجاهل

        crit = all_criteria[crit_id]

        # تحقق من أن المعيار مستحق اليوم
        if crit_id not in due_criteria:
            continue  # معيار غير مستحق اليوم → تجاهل بصمت

        # ── التحقق 3: الدرجة ضمن النطاق المسموح ──
        if score is None or float(score) < 0:
            return jsonify({'message': f'الدرجة غير صحيحة للمعيار: {crit.name}'}), 400
        if float(score) > float(crit.max_score):
            return jsonify({
                'message': f'الدرجة {score} تتجاوز الحد الأقصى {crit.max_score} للمعيار: {crit.name}'
            }), 400

        valid_scores.append({
            'criterion': crit,
            'score': float(score),
            'notes': s.get('notes'),
        })

    # حساب الإجماليات
    total_score = sum(s['score'] for s in valid_scores)
    max_possible = sum(float(s['criterion'].max_score) for s in valid_scores)
    daily_pct = round(total_score / max_possible * 100, 2) if max_possible > 0 else 0

    # إنشاء أو تحديث التقييم اليومي
    if existing:
        evaluation = existing
        # حذف الدرجات القديمة
        KpiCriterionScore.query.filter_by(daily_evaluation_id=existing.id).delete()
        evaluation.template_id        = asgn.template_id
        evaluation.evaluated_by       = user.employee_id
        evaluation.total_score        = total_score
        evaluation.max_possible_score = max_possible
        evaluation.daily_percentage   = daily_pct
        evaluation.notes              = data.get('notes')
        evaluation.status             = 'submitted'
    else:
        evaluation = KpiDailyEvaluation(
            employee_id=employee_id,
            evaluation_date=eval_date,
            template_id=asgn.template_id,
            evaluated_by=user.employee_id,
            total_score=total_score,
            max_possible_score=max_possible,
            daily_percentage=daily_pct,
            notes=data.get('notes'),
            status='submitted',
        )
        db.session.add(evaluation)

    db.session.flush()

    # حفظ درجات المعايير
    for s in valid_scores:
        score_obj = KpiCriterionScore(
            daily_evaluation_id=evaluation.id,
            criterion_id=s['criterion'].id,
            score=s['score'],
            max_score=s['criterion'].max_score,
            notes=s['notes'],
        )
        db.session.add(score_obj)

    db.session.commit()

    # إعادة حساب الملخص الشهري بشكل متزامن
    # (في بيئة إنتاج يُفضّل استخدام queue job)
    try:
        KpiScoringService.compute_monthly_summary(
            employee_id, eval_date.year, eval_date.month
        )
    except Exception:
        pass  # لا يوقف الطلب إذا فشل الحساب

    return jsonify({
        'message': 'تم حفظ التقييم بنجاح',
        'evaluation': evaluation.to_dict(include_scores=True),
    }), 201


@kpi_bp.route('/api/kpi/evaluations/daily/<int:eval_id>', methods=['PUT'])
@token_required
def update_daily_evaluation(user, eval_id):
    """تعديل تقييم يومي (إذا لم يكن معتمداً)."""
    if not _admin_or_manager(user):
        return jsonify({'message': 'غير مصرح لك'}), 403

    evaluation = KpiDailyEvaluation.query.get_or_404(eval_id)

    if not _can_access_employee(user, evaluation.employee_id):
        return jsonify({'message': 'ليس لديك صلاحية لتعديل تقييم هذا الموظف'}), 403

    if evaluation.status == 'approved':
        return jsonify({'message': 'لا يمكن تعديل تقييم معتمد'}), 409

    data = request.get_json() or {}

    # تحديث الملاحظات
    if 'notes' in data:
        evaluation.notes = data['notes']

    # تحديث الدرجات إن أُرسلت
    scores_data = data.get('scores', [])
    if scores_data:
        asgn = KpiScoringService.get_active_assignment(
            evaluation.employee_id, evaluation.evaluation_date
        )
        due_criteria = {
            c.id: c for c in KpiFrequencyService.get_due_criteria(
                evaluation.template_id, evaluation.employee_id,
                evaluation.evaluation_date,
                asgn.start_date if asgn else None,
            )
        }

        KpiCriterionScore.query.filter_by(daily_evaluation_id=eval_id).delete()
        total_score = 0.0
        max_possible = 0.0
        for s in scores_data:
            crit_id = s.get('criterion_id')
            crit = due_criteria.get(crit_id)
            if not crit:
                continue
            score = float(s.get('score', 0))
            score = min(score, float(crit.max_score))
            total_score  += score
            max_possible += float(crit.max_score)
            db.session.add(KpiCriterionScore(
                daily_evaluation_id=eval_id,
                criterion_id=crit_id,
                score=score,
                max_score=crit.max_score,
                notes=s.get('notes'),
            ))

        evaluation.total_score        = total_score
        evaluation.max_possible_score = max_possible
        evaluation.daily_percentage   = round(total_score / max_possible * 100, 2) if max_possible > 0 else 0

    db.session.commit()

    # إعادة حساب الملخص الشهري
    try:
        KpiScoringService.compute_monthly_summary(
            evaluation.employee_id,
            evaluation.evaluation_date.year,
            evaluation.evaluation_date.month,
        )
    except Exception:
        pass

    return jsonify(evaluation.to_dict(include_scores=True)), 200


@kpi_bp.route('/api/kpi/evaluations/monthly-calendar', methods=['GET'])
@token_required
def monthly_calendar(user):
    """
    تقويم شهري: لكل يوم → حالة الحضور + حالة التقييم + نسبة يومية.
    ?employee_id=X&year=Y&month=M
    """
    employee_id = request.args.get('employee_id', type=int)
    year  = request.args.get('year', type=int)
    month = request.args.get('month', type=int)

    if not all([employee_id, year, month]):
        return jsonify({'message': 'employee_id و year و month مطلوبة'}), 400

    if not _can_access_employee(user, employee_id):
        return jsonify({'message': 'ليس لديك صلاحية للوصول لبيانات هذا الموظف'}), 403

    calendar_data = KpiScoringService.get_month_calendar(employee_id, year, month)
    return jsonify(calendar_data), 200


# ═══════════════════════════════════════════════════════════════════════
# SECTION E — الملخص الشهري (Monthly Summary)
# ═══════════════════════════════════════════════════════════════════════

@kpi_bp.route('/api/kpi/summaries/monthly', methods=['GET'])
@token_required
def get_monthly_summary(user):
    """
    جلب الملخص الشهري لموظف.
    ?employee_id=X&year=Y&month=M
    """
    employee_id = request.args.get('employee_id', type=int)
    year  = request.args.get('year', type=int)
    month = request.args.get('month', type=int)

    if not all([employee_id, year, month]):
        return jsonify({'message': 'employee_id و year و month مطلوبة'}), 400

    # التحقق من صلاحية الوصول:
    # - admin/manager: يرى فقط موظفيه
    # - موظف عادي: يرى نفسه فقط إذا كان allow_self_view مفعّلاً
    if _admin_or_manager(user):
        if not _can_access_employee(user, employee_id):
            return jsonify({'message': 'ليس لديك صلاحية لعرض ملخص هذا الموظف'}), 403
    else:
        settings = KpiSettings.get()
        if not settings.allow_self_view or user.employee_id != employee_id:
            return jsonify({'message': 'غير مصرح لك بعرض هذا التقرير'}), 403

    summary = KpiMonthlySummary.query.filter_by(
        employee_id=employee_id,
        year=year,
        month=month,
    ).first()

    if not summary:
        # محاولة الحساب إذا لم يوجد ملخص
        summary = KpiScoringService.compute_monthly_summary(employee_id, year, month)
        if not summary:
            return jsonify({'message': 'لا يوجد ملخص شهري لهذا الموظف في هذه الفترة'}), 404

    # إضافة تفاصيل التقييمات اليومية
    evaluations = KpiDailyEvaluation.query.filter(
        KpiDailyEvaluation.employee_id == employee_id,
        extract('year',  KpiDailyEvaluation.evaluation_date) == year,
        extract('month', KpiDailyEvaluation.evaluation_date) == month,
    ).order_by(KpiDailyEvaluation.evaluation_date).all()

    # متوسط كل معيار عبر الشهر
    criterion_totals = {}
    for ev in evaluations:
        for s in ev.scores.all():
            if s.criterion_id not in criterion_totals:
                criterion_totals[s.criterion_id] = {
                    'name': s.criterion.name if s.criterion else '',
                    'total': 0.0,
                    'max_total': 0.0,
                    'count': 0,
                }
            criterion_totals[s.criterion_id]['total']     += float(s.score)
            criterion_totals[s.criterion_id]['max_total'] += float(s.max_score)
            criterion_totals[s.criterion_id]['count']     += 1

    criterion_averages = []
    for cid, vals in criterion_totals.items():
        avg_pct = round(vals['total'] / vals['max_total'] * 100, 1) if vals['max_total'] > 0 else 0
        criterion_averages.append({
            'criterion_id': cid,
            'name': vals['name'],
            'avg_percentage': avg_pct,
            'total_score': vals['total'],
            'max_total': vals['max_total'],
            'days_evaluated': vals['count'],
        })

    return jsonify({
        'summary': summary.to_dict(),
        'daily_evaluations': [ev.to_dict(include_scores=True) for ev in evaluations],
        'criterion_averages': sorted(criterion_averages, key=lambda x: -x['avg_percentage']),
    }), 200


@kpi_bp.route('/api/kpi/summaries/monthly/recompute', methods=['POST'])
@token_required
def recompute_monthly_summary(user):
    """إعادة حساب الملخص الشهري يدوياً."""
    if not _admin_or_manager(user):
        return jsonify({'message': 'غير مصرح لك'}), 403

    data = request.get_json() or {}
    employee_id = data.get('employee_id')
    year  = data.get('year')
    month = data.get('month')

    if not all([employee_id, year, month]):
        return jsonify({'message': 'employee_id و year و month مطلوبة'}), 400

    if not _can_access_employee(user, int(employee_id)):
        return jsonify({'message': 'ليس لديك صلاحية لإعادة حساب ملخص هذا الموظف'}), 403

    summary = KpiScoringService.compute_monthly_summary(int(employee_id), int(year), int(month))
    if not summary:
        return jsonify({'message': 'لا يوجد قالب مرتبط بهذا الموظف في هذه الفترة'}), 404

    return jsonify({'message': 'تم إعادة الحساب بنجاح', 'summary': summary.to_dict()}), 200


@kpi_bp.route('/api/kpi/summaries/monthly/<int:summary_id>/finalize', methods=['PUT'])
@token_required
def finalize_monthly_summary(user, summary_id):
    """اعتماد الملخص الشهري مع تعليق المدير."""
    if not _admin_or_manager(user):
        return jsonify({'message': 'غير مصرح لك'}), 403

    summary = KpiMonthlySummary.query.get_or_404(summary_id)

    if not _can_access_employee(user, summary.employee_id):
        return jsonify({'message': 'ليس لديك صلاحية لاعتماد ملخص هذا الموظف'}), 403

    data = request.get_json() or {}

    summary.manager_comment = data.get('manager_comment', summary.manager_comment)
    summary.is_finalized    = True
    db.session.commit()
    return jsonify({'message': 'تم اعتماد الملخص الشهري', 'summary': summary.to_dict()}), 200


# ═══════════════════════════════════════════════════════════════════════
# SECTION F — التقارير (Reports)
# ═══════════════════════════════════════════════════════════════════════

@kpi_bp.route('/api/kpi/reports/employee', methods=['GET'])
@token_required
def report_employee(user):
    """
    تقرير موظف: ملخصات شهرية + اتجاه الأداء.
    ?employee_id=X&from=YYYY-MM&to=YYYY-MM
    """
    employee_id = request.args.get('employee_id', type=int)
    from_str = request.args.get('from')  # YYYY-MM
    to_str   = request.args.get('to')    # YYYY-MM

    if not employee_id:
        return jsonify({'message': 'employee_id مطلوب'}), 400

    # التحقق من صلاحية الوصول
    if _admin_or_manager(user):
        if not _can_access_employee(user, employee_id):
            return jsonify({'message': 'ليس لديك صلاحية لعرض تقرير هذا الموظف'}), 403
    else:
        settings = KpiSettings.get()
        if not settings.allow_self_view or user.employee_id != employee_id:
            return jsonify({'message': 'غير مصرح لك'}), 403

    q = KpiMonthlySummary.query.filter_by(employee_id=employee_id)

    if from_str:
        try:
            fy, fm = int(from_str[:4]), int(from_str[5:7])
            q = q.filter(
                db.or_(
                    KpiMonthlySummary.year > fy,
                    db.and_(KpiMonthlySummary.year == fy, KpiMonthlySummary.month >= fm)
                )
            )
        except Exception:
            pass

    if to_str:
        try:
            ty, tm = int(to_str[:4]), int(to_str[5:7])
            q = q.filter(
                db.or_(
                    KpiMonthlySummary.year < ty,
                    db.and_(KpiMonthlySummary.year == ty, KpiMonthlySummary.month <= tm)
                )
            )
        except Exception:
            pass

    summaries = q.order_by(KpiMonthlySummary.year, KpiMonthlySummary.month).all()
    employee  = Employee.query.get(employee_id)

    return jsonify({
        'employee': {
            'id': employee.id,
            'name': employee.full_name,
        } if employee else None,
        'summaries': [s.to_dict() for s in summaries],
        'trend': [
            {
                'label': f"{s.year}-{s.month:02d}",
                'percentage': float(s.monthly_percentage or 0),
                'grade': s.performance_grade,
            }
            for s in summaries
        ],
    }), 200


@kpi_bp.route('/api/kpi/reports/department', methods=['GET'])
@token_required
def report_department(user):
    """
    تقرير قسم: جميع موظفي القسم مع نسب الأداء الشهرية.
    ?department_id=X&year=Y&month=M
    """
    dept_id = request.args.get('department_id', type=int)
    year    = request.args.get('year', type=int)
    month   = request.args.get('month', type=int)

    if not all([dept_id, year, month]):
        return jsonify({'message': 'department_id و year و month مطلوبة'}), 400

    # التحقق: رئيس القسم يرى قسمه فقط، رئيس الفرع يرى أقسام فرعه فقط
    if not _is_admin(user):
        accessible_ids = _get_accessible_employee_ids(user)
        # نتحقق أن القسم المطلوب يحتوي على موظفين ضمن نطاق المستخدم
        dept_employees = Employee.query.filter_by(department_id=dept_id).all()
        dept_emp_ids   = [e.id for e in dept_employees]
        if not any(eid in accessible_ids for eid in dept_emp_ids):
            return jsonify({'message': 'ليس لديك صلاحية لعرض تقرير هذا القسم'}), 403

    employees = Employee.query.filter_by(department_id=dept_id).all()
    # تصفية الموظفين حسب نطاق صلاحية المستخدم
    if not _is_admin(user):
        accessible_ids = _get_accessible_employee_ids(user)
        employees = [e for e in employees if e.id in accessible_ids]
    result = []
    total_pct = 0.0
    count = 0

    for emp in employees:
        summary = KpiMonthlySummary.query.filter_by(
            employee_id=emp.id,
            year=year,
            month=month,
        ).first()

        pct = float(summary.monthly_percentage) if summary else None
        if pct is not None:
            total_pct += pct
            count += 1

        result.append({
            'employee_id': emp.id,
            'employee_name': emp.full_name,
            'summary': summary.to_dict() if summary else None,
            'monthly_percentage': pct,
            'performance_grade': summary.performance_grade if summary else 'not_evaluated',
        })

    dept_avg = round(total_pct / count, 2) if count > 0 else None

    return jsonify({
        'department_id': dept_id,
        'year': year,
        'month': month,
        'department_average': dept_avg,
        'employees': result,
    }), 200


@kpi_bp.route('/api/kpi/reports/comparison', methods=['GET'])
@token_required
def report_comparison(user):
    """
    مقارنة أداء عدة موظفين في شهر واحد.
    ?employee_ids[]=1&employee_ids[]=2&year=Y&month=M
    """
    employee_ids = request.args.getlist('employee_ids[]', type=int)
    year  = request.args.get('year', type=int)
    month = request.args.get('month', type=int)

    if not employee_ids or not year or not month:
        return jsonify({'message': 'employee_ids و year و month مطلوبة'}), 400

    # تصفية حسب نطاق الصلاحيات قبل تطبيق الحد الأقصى
    if not _is_admin(user):
        accessible_ids = _get_accessible_employee_ids(user)
        employee_ids = [eid for eid in employee_ids if eid in accessible_ids]

    # حد أقصى 5 موظفين
    employee_ids = employee_ids[:5]

    result = []
    for emp_id in employee_ids:
        emp = Employee.query.get(emp_id)
        if not emp:
            continue
        summary = KpiMonthlySummary.query.filter_by(
            employee_id=emp_id,
            year=year,
            month=month,
        ).first()
        result.append({
            'employee_id': emp_id,
            'employee_name': emp.full_name if emp else None,
            'monthly_percentage': float(summary.monthly_percentage) if summary else 0,
            'performance_grade': summary.performance_grade if summary else 'not_evaluated',
            'evaluated_days': summary.evaluated_days if summary else 0,
        })

    return jsonify({'year': year, 'month': month, 'employees': result}), 200


@kpi_bp.route('/api/kpi/reports/company-overview', methods=['GET'])
@token_required
def report_company_overview(user):
    """
    نظرة عامة على الأداء للشركة في شهر معين.
    ?year=Y&month=M
    """
    year  = request.args.get('year', type=int)
    month = request.args.get('month', type=int)

    if not year or not month:
        return jsonify({'message': 'year و month مطلوبان'}), 400

    # admin → يرى الكل | المديرون → يرون موظفيهم فقط
    q = KpiMonthlySummary.query.filter_by(year=year, month=month)
    if not _is_admin(user):
        accessible_ids = _get_accessible_employee_ids(user)
        q = q.filter(KpiMonthlySummary.employee_id.in_(accessible_ids))

    summaries = q.all()

    grade_counts = {'excellent': 0, 'good': 0, 'average': 0, 'poor': 0, 'not_evaluated': 0}
    for s in summaries:
        grade = s.performance_grade or 'not_evaluated'
        grade_counts[grade] = grade_counts.get(grade, 0) + 1

    # أعلى 5 وأقل 5 موظفين
    sorted_summaries = sorted(
        [s for s in summaries if s.performance_grade != 'not_evaluated'],
        key=lambda x: float(x.monthly_percentage or 0),
        reverse=True
    )
    top5    = [s.to_dict() for s in sorted_summaries[:5]]
    bottom5 = [s.to_dict() for s in sorted_summaries[-5:]]

    total_pct = sum(float(s.monthly_percentage or 0) for s in summaries)
    overall_avg = round(total_pct / len(summaries), 2) if summaries else 0

    return jsonify({
        'year': year,
        'month': month,
        'total_employees_evaluated': len(summaries),
        'overall_average_percentage': overall_avg,
        'grade_distribution': grade_counts,
        'top_5': top5,
        'bottom_5': bottom5,
    }), 200


# ═══════════════════════════════════════════════════════════════════════
# SECTION G — الإعدادات (Settings)
# ═══════════════════════════════════════════════════════════════════════

@kpi_bp.route('/api/kpi/settings', methods=['GET'])
@token_required
def get_settings(user):
    """جلب إعدادات KPI."""
    settings = KpiSettings.get()
    return jsonify(settings.to_dict()), 200


@kpi_bp.route('/api/kpi/settings', methods=['PUT'])
@token_required
def update_settings(user):
    """تحديث إعدادات KPI."""
    if not _is_admin(user):
        return jsonify({'message': 'يُسمح للمدير العام فقط بتعديل الإعدادات'}), 403

    settings = KpiSettings.get()
    data = request.get_json() or {}

    if 'excellent_threshold' in data:
        settings.excellent_threshold = data['excellent_threshold']
    if 'good_threshold' in data:
        settings.good_threshold = data['good_threshold']
    if 'average_threshold' in data:
        settings.average_threshold = data['average_threshold']
    if 'default_max_score' in data:
        settings.default_max_score = data['default_max_score']
    if 'allow_self_view' in data:
        settings.allow_self_view = data['allow_self_view']

    settings.updated_by = user.employee_id
    db.session.commit()
    return jsonify(settings.to_dict()), 200
