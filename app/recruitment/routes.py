# app/recruitment/routes.py
# Blueprint التوظيف - جميع نقاط النهاية /api/recruitment/...

import json
from flask import Blueprint, request, jsonify, send_file

from app import db
from app.utils import token_required
from app.recruitment.models import (
    RecruitmentFormSection,
    RecruitmentFormField,
    RecruitmentApplication,
    HeadcountTarget,
    ALLOWED_FIELD_TYPES,
    ALLOWED_STATUSES,
)
from app.recruitment.services.application_service import (
    create_application,
    get_application_with_answers,
    get_applications_list,
    update_application,
    delete_application,
)
from app.recruitment.services.status_service import (
    update_application_status,
    process_hire,
)
from app.recruitment.services.headcount_service import (
    check_headcount_and_notify,
    check_all_targets,
    get_headcount_status,
)
from app.recruitment.services.employee_mapper import VALID_EMPLOYEE_FIELDS
from app.recruitment.seed_data import seed_default_form
from app.recruitment.reports import export_excel, export_pdf

recruitment_bp = Blueprint('recruitment', __name__, url_prefix='/api/recruitment')


# ═══════════════════════════════════════════════════════════════════
# FORM CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

@recruitment_bp.route('/form/sections', methods=['GET'])
@token_required
def get_form_sections(user):
    """إرجاع كل أقسام النموذج مع حقولها"""
    sections = (
        RecruitmentFormSection.query
        .order_by(RecruitmentFormSection.display_order)
        .all()
    )
    return jsonify([s.to_dict(include_fields=True) for s in sections]), 200


@recruitment_bp.route('/form/sections', methods=['POST'])
@token_required
def create_form_section(user):
    """إنشاء قسم جديد في النموذج (admin فقط)"""
    if not user.is_super_admin():
        return jsonify({'message': 'غير مصرح'}), 403

    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'message': 'اسم القسم مطلوب'}), 400

    new_order = data.get('display_order', 0)

    # إزاحة الأقسام التي ترتيبها >= الترتيب الجديد لإفساح المكان
    RecruitmentFormSection.query.filter(
        RecruitmentFormSection.display_order >= new_order
    ).update(
        {RecruitmentFormSection.display_order: RecruitmentFormSection.display_order + 1},
        synchronize_session=False
    )

    section = RecruitmentFormSection(
        name=data['name'],
        display_order=new_order,
        is_active=data.get('is_active', True),
    )
    db.session.add(section)
    db.session.commit()
    return jsonify(section.to_dict()), 201


@recruitment_bp.route('/form/sections/<int:section_id>', methods=['PUT'])
@token_required
def update_form_section(user, section_id):
    """تحديث قسم في النموذج"""
    if not user.is_super_admin():
        return jsonify({'message': 'غير مصرح'}), 403

    section = RecruitmentFormSection.query.get_or_404(section_id)
    data = request.get_json()

    if 'name' in data:
        section.name = data['name']
    if 'display_order' in data and data['display_order'] != section.display_order:
        new_order = data['display_order']
        # إزاحة الأقسام الأخرى التي ترتيبها >= الترتيب الجديد (باستثناء القسم الحالي)
        RecruitmentFormSection.query.filter(
            RecruitmentFormSection.id != section.id,
            RecruitmentFormSection.display_order >= new_order
        ).update(
            {RecruitmentFormSection.display_order: RecruitmentFormSection.display_order + 1},
            synchronize_session=False
        )
        section.display_order = new_order
    if 'is_active' in data:
        section.is_active = data['is_active']

    db.session.commit()
    return jsonify(section.to_dict()), 200


@recruitment_bp.route('/form/fields', methods=['POST'])
@token_required
def create_form_field(user):
    """إضافة حقل جديد للنموذج"""
    if not user.is_super_admin():
        return jsonify({'message': 'غير مصرح'}), 403

    data = request.get_json()
    required = ['section_id', 'field_key', 'label', 'field_type', 'display_order']
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({'message': f'الحقول المطلوبة مفقودة: {", ".join(missing)}'}), 400

    # التحقق من نوع الحقل
    if data['field_type'] not in ALLOWED_FIELD_TYPES:
        return jsonify({
            'message': f"نوع الحقل غير مسموح به. الأنواع المتاحة: {ALLOWED_FIELD_TYPES}"
        }), 400

    # التحقق من فريدة field_key
    if RecruitmentFormField.query.filter_by(field_key=data['field_key']).first():
        return jsonify({'message': f"field_key '{data['field_key']}' مستخدم مسبقاً"}), 409

    # التحقق من maps_to_employee_field إذا كان موجوداً
    if data.get('maps_to_employee_field'):
        if data['maps_to_employee_field'] not in VALID_EMPLOYEE_FIELDS:
            return jsonify({
                'message': f"maps_to_employee_field '{data['maps_to_employee_field']}' غير موجود في جدول الموظفين",
                'valid_values': list(VALID_EMPLOYEE_FIELDS)
            }), 400

    # تحويل options إلى JSON إذا كانت قائمة
    options_val = None
    if data.get('options'):
        opts = data['options']
        options_val = json.dumps(opts, ensure_ascii=False) if isinstance(opts, list) else opts

    # إزاحة الحقول في نفس القسم التي ترتيبها >= الترتيب الجديد لإفساح المكان
    RecruitmentFormField.query.filter(
        RecruitmentFormField.section_id == data['section_id'],
        RecruitmentFormField.display_order >= data['display_order']
    ).update(
        {RecruitmentFormField.display_order: RecruitmentFormField.display_order + 1},
        synchronize_session=False
    )

    field = RecruitmentFormField(
        section_id=data['section_id'],
        field_key=data['field_key'],
        label=data['label'],
        field_type=data['field_type'],
        options=options_val,
        is_required=data.get('is_required', False),
        is_active=data.get('is_active', True),
        display_order=data['display_order'],
        maps_to_employee_field=data.get('maps_to_employee_field'),
        is_searchable=data.get('is_searchable', False),
        is_system_field=False,
    )
    db.session.add(field)
    db.session.commit()
    return jsonify(field.to_dict()), 201


@recruitment_bp.route('/form/fields/<int:field_id>', methods=['PUT'])
@token_required
def update_form_field(user, field_id):
    """تحديث حقل في النموذج"""
    if not user.is_super_admin():
        return jsonify({'message': 'غير مصرح'}), 403

    field = RecruitmentFormField.query.get_or_404(field_id)
    data = request.get_json()

    # field_key لا يتغير للحقول الأساسية
    if 'field_key' in data and field.is_system_field:
        return jsonify({'message': 'لا يمكن تعديل field_key للحقول الأساسية'}), 400

    # field_type لا يتغير إذا كانت هناك إجابات موجودة
    if 'field_type' in data and data['field_type'] != field.field_type:
        if data['field_type'] not in ALLOWED_FIELD_TYPES:
            return jsonify({'message': f"نوع الحقل غير مسموح به"}), 400
        answers_count = field.answers.count()
        if answers_count > 0:
            return jsonify({
                'message': f"لا يمكن تغيير نوع الحقل لأن هناك {answers_count} إجابة موجودة"
            }), 409
        field.field_type = data['field_type']

    if 'label' in data:
        field.label = data['label']
    if 'section_id' in data:
        field.section_id = data['section_id']

    if 'display_order' in data and (
        data['display_order'] != field.display_order or 'section_id' in data
    ):
        new_order = data['display_order']
        # القسم المستهدف (قد يكون تغيّر للتو في الأعلى)
        target_section_id = field.section_id
        # إزاحة الحقول الأخرى في القسم المستهدف التي ترتيبها >= الترتيب الجديد
        RecruitmentFormField.query.filter(
            RecruitmentFormField.id != field.id,
            RecruitmentFormField.section_id == target_section_id,
            RecruitmentFormField.display_order >= new_order
        ).update(
            {RecruitmentFormField.display_order: RecruitmentFormField.display_order + 1},
            synchronize_session=False
        )
        field.display_order = new_order
    if 'is_required' in data:
        field.is_required = data['is_required']
    if 'is_active' in data:
        field.is_active = data['is_active']
    if 'is_searchable' in data:
        field.is_searchable = data['is_searchable']
    if 'options' in data:
        opts = data['options']
        field.options = json.dumps(opts, ensure_ascii=False) if isinstance(opts, list) else opts
    if 'maps_to_employee_field' in data:
        val = data['maps_to_employee_field']
        if val and val not in VALID_EMPLOYEE_FIELDS:
            return jsonify({
                'message': f"maps_to_employee_field '{val}' غير موجود في جدول الموظفين",
                'valid_values': list(VALID_EMPLOYEE_FIELDS)
            }), 400
        field.maps_to_employee_field = val

    db.session.commit()
    return jsonify(field.to_dict()), 200


@recruitment_bp.route('/form/fields/<int:field_id>', methods=['DELETE'])
@token_required
def delete_form_field(user, field_id):
    """حذف حقل من النموذج"""
    if not user.is_super_admin():
        return jsonify({'message': 'غير مصرح'}), 403

    field = RecruitmentFormField.query.get_or_404(field_id)

    if field.is_system_field:
        return jsonify({'message': 'لا يمكن حذف الحقول الأساسية'}), 400

    answers_count = field.answers.count()
    if answers_count > 0:
        return jsonify({
            'message': f"لا يمكن حذف الحقل لأن هناك {answers_count} إجابة مرتبطة به",
            'answers_count': answers_count
        }), 409

    db.session.delete(field)
    db.session.commit()
    return jsonify({'message': 'تم حذف الحقل بنجاح'}), 200


@recruitment_bp.route('/form/render', methods=['GET'])
@token_required
def render_form(user):
    """
    إرجاع هيكل النموذج الكامل جاهزاً للعرض في الواجهة.
    فقط الأقسام والحقول النشطة، مرتبة حسب display_order.
    """
    sections = (
        RecruitmentFormSection.query
        .filter_by(is_active=True)
        .order_by(RecruitmentFormSection.display_order)
        .all()
    )

    result = []
    for section in sections:
        fields = (
            RecruitmentFormField.query
            .filter_by(section_id=section.id, is_active=True)
            .order_by(RecruitmentFormField.display_order)
            .all()
        )
        result.append({
            'id': section.id,
            'name': section.name,
            'display_order': section.display_order,
            'fields': [f.to_dict() for f in fields],
        })

    return jsonify({'sections': result}), 200


@recruitment_bp.route('/setup/seed-form', methods=['POST'])
@token_required
def seed_form(user):
    """زرع بيانات النموذج الافتراضي (super_admin فقط)"""
    if not user.is_super_admin():
        return jsonify({'message': 'غير مصرح'}), 403

    success, message = seed_default_form()
    status_code = 201 if success else 200
    return jsonify({'message': message, 'seeded': success}), status_code


# ═══════════════════════════════════════════════════════════════════
# APPLICATIONS
# ═══════════════════════════════════════════════════════════════════

@recruitment_bp.route('/applications', methods=['POST'])
@token_required
def create_application_route(user):
    """إنشاء طلب توظيف جديد"""
    data = request.get_json()
    if not data:
        return jsonify({'message': 'البيانات مطلوبة'}), 400

    # ── تشخيص مؤقت: لطباعة ما يصل من الفرونت بخصوص الخبرات ──
    print('[RECRUITMENT][CREATE] payload keys =', list(data.keys()))
    print('[RECRUITMENT][CREATE] experiences =', data.get('experiences'))
    print('[RECRUITMENT][CREATE] experiences type =', type(data.get('experiences')).__name__)

    if not data.get('applied_position'):
        return jsonify({'message': 'الوظيفة المطلوبة مطلوبة'}), 400

    application, result = create_application(data, user.id)

    if application is None:
        # result هو dict بالأخطاء
        return jsonify({'message': 'فشل التحقق من البيانات', 'errors': result.get('errors', [])}), 400

    response = {
        'message': 'تم إنشاء الطلب بنجاح',
        'application': application.to_dict(),
    }

    if result and result.get('type') == 'duplicate_phone':
        response['warning'] = 'duplicate_phone'
        response['existing_application_id'] = result.get('existing_application_id')

    return jsonify(response), 201


@recruitment_bp.route('/applications', methods=['GET'])
@token_required
def get_applications_route(user):
    """قائمة الطلبات مع الفلترة والتقسيم"""
    args = request.args

    # بناء قاموس الفلاتر من query params
    filters = {}
    if args.get('status'):
        filters['status'] = args['status']
    if args.get('branch_id'):
        filters['branch_id'] = int(args['branch_id'])
    if args.get('department_id'):
        filters['department_id'] = int(args['department_id'])

    # الفلاتر الديناميكية (الحقول القابلة للبحث)
    from app.recruitment.models import RecruitmentFormField
    searchable_keys = {
        f.field_key for f in RecruitmentFormField.query.filter_by(
            is_searchable=True, is_active=True
        ).all()
    }
    for key in searchable_keys:
        if args.get(key):
            filters[key] = args[key]

    page = int(args.get('page', 1))
    per_page = int(args.get('per_page', 20))

    result = get_applications_list(filters=filters, page=page, per_page=per_page)
    return jsonify(result), 200


@recruitment_bp.route('/applications/<int:application_id>', methods=['GET'])
@token_required
def get_application_route(user, application_id):
    """تفاصيل طلب واحد مع كل إجاباته"""
    result = get_application_with_answers(application_id)
    if not result:
        return jsonify({'message': 'الطلب غير موجود'}), 404

    # ── تشخيص مؤقت ──
    exps = result.get('experiences') or []
    print(f'[RECRUITMENT][GET] app={application_id} experiences_count={len(exps)}')

    return jsonify(result), 200


@recruitment_bp.route('/applications/<int:application_id>', methods=['PUT'])
@token_required
def update_application_route(user, application_id):
    """تحديث بيانات طلب"""
    data = request.get_json()

    # ── تشخيص مؤقت ──
    print('[RECRUITMENT][UPDATE]', application_id, 'payload keys =', list((data or {}).keys()))
    print('[RECRUITMENT][UPDATE] experiences =', (data or {}).get('experiences'))
    print('[RECRUITMENT][UPDATE] experiences type =', type((data or {}).get('experiences')).__name__)

    application, error = update_application(application_id, data)
    if error:
        return jsonify({'message': error}), 400 if 'غير موجود' not in error else 404

    # نُرجع الطلب مع كل تفاصيله (experiences ضمنها) لتبسيط تحديث الفرونت بعد الحفظ
    full = get_application_with_answers(application_id)
    return jsonify({'message': 'تم التحديث بنجاح', **(full or {'application': application.to_dict()})}), 200


@recruitment_bp.route('/applications/<int:application_id>', methods=['DELETE'])
@token_required
def delete_application_route(user, application_id):
    """حذف طلب"""
    if not user.is_super_admin():
        return jsonify({'message': 'غير مصرح'}), 403

    success, error = delete_application(application_id)
    if not success:
        return jsonify({'message': error}), 404
    return jsonify({'message': 'تم الحذف بنجاح'}), 200


# ═══════════════════════════════════════════════════════════════════
# STATUS & DECISIONS
# ═══════════════════════════════════════════════════════════════════

@recruitment_bp.route('/applications/<int:application_id>/status', methods=['PATCH'])
@token_required
def update_status_route(user, application_id):
    """تحديث حالة طلب مع تطبيق قواعد الانتقال"""
    data = request.get_json()
    if not data or not data.get('status'):
        return jsonify({'message': 'الحالة مطلوبة'}), 400

    extra = {
        'rejection_reason': data.get('rejection_reason'),
        'evaluation_score': data.get('evaluation_score'),
    }

    application, error = update_application_status(
        application_id=application_id,
        new_status=data['status'],
        extra_data=extra,
        acting_user_id=user.id
    )

    if error:
        code = 404 if 'غير موجود' in error else 400
        return jsonify({'message': error}), code

    return jsonify({
        'message': 'تم تحديث الحالة بنجاح',
        'application': application.to_dict()
    }), 200


@recruitment_bp.route('/applications/<int:application_id>/hire', methods=['POST'])
@token_required
def hire_application_route(user, application_id):
    """
    معالجة قرار التعيين وإنشاء الموظف.

    يدعم نوعين من الطلبات:
    - application/json: بيانات التعيين فقط (كما كان سابقاً).
    - multipart/form-data: بيانات التعيين + صورة اختيارية في الحقل 'photo'،
      بنفس آلية رفع صورة الموظف عند إضافة موظف جديد (مرفق label=employee_photo).
    """
    photo_file = None
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form.to_dict()
        photo_file = request.files.get('photo')
        # تحويل الحقول الرقمية القادمة كنصوص من multipart
        for int_field in ('branch_id', 'department_id', 'job_title_id',
                          'shift_id', 'profession_id'):
            if data.get(int_field) not in (None, ''):
                try:
                    data[int_field] = int(data[int_field])
                except (TypeError, ValueError):
                    return jsonify({'message': f"قيمة '{int_field}' غير صالحة"}), 400

    if not data:
        return jsonify({'message': 'البيانات مطلوبة'}), 400

    result, error = process_hire(
        application_id=application_id,
        hiring_data=data,
        acting_user_id=user.id
    )

    if error:
        code = 404 if 'غير موجود' in error else 400
        return jsonify({'message': error}), code

    # حفظ صورة التعيين (إن أُرسلت) كمرفق للموظف بنفس آلية إضافة موظف جديد
    photo_attachment_id = None
    employee_id = result.get('employee_id')
    if photo_file and employee_id:
        from app.models.employee import Employee
        from app.routes.employee import _save_employee_photo

        employee = Employee.query.get(employee_id)
        if employee:
            attachment = _save_employee_photo(employee, photo_file)
            if attachment:
                photo_attachment_id = attachment.id

    return jsonify({
        'message': 'تم تعيين المتقدم بنجاح',
        'photo_attachment_id': photo_attachment_id,
        **result
    }), 200


# ═══════════════════════════════════════════════════════════════════
# HIRING LOOKUPS — بيانات مرجعية لنموذج التعيين
# ═══════════════════════════════════════════════════════════════════

@recruitment_bp.route('/hiring-lookups', methods=['GET'])
@token_required
def get_hiring_lookups(user):
    """
    إرجاع كل البيانات المرجعية اللازمة لنموذج التعيين دفعة واحدة:
    المسميات الوظيفية، الورديات، المهن، الفروع، الأقسام
    """
    from app.models.job_title import JobTitle
    from app.models.shift import Shift
    from app.models.profession import Profession
    from app.models.branch import Branch
    from app.models.department import Department

    job_titles = JobTitle.query.all()
    shifts = Shift.query.all()
    professions = Profession.query.all()
    branches = Branch.query.all()
    departments = Department.query.all()

    return jsonify({
        'job_titles': [
            {
                'id': jt.id,
                'title_name': jt.title_name,
                'shift_system': jt.shift_system,
                'production_system': jt.production_system,
                'month_system': jt.month_system,
            }
            for jt in job_titles
        ],
        'shifts': [
            {'id': s.id, 'name': s.name}
            for s in shifts
        ],
        'professions': [
            {'id': p.id, 'name': p.name}
            for p in professions
        ],
        'branches': [
            {'id': b.id, 'name': b.name}
            for b in branches
        ],
        'departments': [
            {'id': d.id, 'name': d.name}
            for d in departments
        ],
    }), 200


@recruitment_bp.route('/hiring-lookups/departments-by-branch/<int:branch_id>', methods=['GET'])
@token_required
def get_departments_by_branch(user, branch_id):
    """إرجاع الأقسام المتاحة في فرع معين"""
    from app.models.department import BranchDepartment, Department

    branch_depts = (
        BranchDepartment.query
        .filter_by(branch_id=branch_id)
        .all()
    )
    dept_ids = [bd.department_id for bd in branch_depts]
    departments = Department.query.filter(Department.id.in_(dept_ids)).all() if dept_ids else []

    return jsonify([
        {'id': d.id, 'name': d.name}
        for d in departments
    ]), 200


@recruitment_bp.route('/hiring-lookups/work-systems/<int:job_title_id>', methods=['GET'])
@token_required
def get_work_systems_for_job_title(user, job_title_id):
    """
    إرجاع أنظمة العمل المتاحة حسب المسمى الوظيفي.
    المسمى الوظيفي يحدد أي أنظمة مفعَّلة (shift_system, production_system, month_system).
    """
    from app.models.job_title import JobTitle

    jt = JobTitle.query.get_or_404(job_title_id)

    systems = []
    if jt.month_system:
        systems.append({'value': 'monthly', 'label': 'نظام شهري'})
    if jt.shift_system:
        systems.append({'value': 'shift', 'label': 'نظام ورديات'})
    if jt.production_system:
        systems.append({'value': 'production', 'label': 'نظام إنتاج'})

    # إذا لم يكن أي نظام مفعَّل نضيف الشهري كافتراضي
    if not systems:
        systems.append({'value': 'monthly', 'label': 'نظام شهري'})

    return jsonify({
        'job_title_id': jt.id,
        'title_name': jt.title_name,
        'shift_system': jt.shift_system,
        'work_systems': systems,
    }), 200


# ═══════════════════════════════════════════════════════════════════
# HEADCOUNT TARGETS
# ═══════════════════════════════════════════════════════════════════

@recruitment_bp.route('/headcount-targets', methods=['GET'])
@token_required
def get_headcount_targets(user):
    """قائمة أهداف الاستيعاب"""
    targets = HeadcountTarget.query.all()
    return jsonify([t.to_dict() for t in targets]), 200


@recruitment_bp.route('/headcount-targets', methods=['POST'])
@token_required
def create_headcount_target(user):
    """إنشاء هدف استيعاب جديد"""
    if not user.is_super_admin():
        return jsonify({'message': 'غير مصرح'}), 403

    data = request.get_json()

    branch_id = data.get('branch_id')
    department_id = data.get('department_id')

    if not branch_id and not department_id:
        return jsonify({'message': 'يجب تحديد فرع أو قسم على الأقل'}), 400

    if not data.get('target_count'):
        return jsonify({'message': 'العدد المستهدف مطلوب'}), 400

    # التحقق من عدم التكرار
    existing = HeadcountTarget.query.filter_by(
        branch_id=branch_id,
        department_id=department_id
    ).first()
    if existing:
        return jsonify({'message': 'يوجد هدف مسبق لهذا الفرع/القسم'}), 409

    target = HeadcountTarget(
        branch_id=branch_id,
        department_id=department_id,
        target_count=int(data['target_count']),
        warning_threshold=int(data.get('warning_threshold', 1)),
        notes=data.get('notes'),
        created_by=user.id,
    )
    db.session.add(target)
    db.session.commit()
    return jsonify(target.to_dict()), 201


@recruitment_bp.route('/headcount-targets/<int:target_id>', methods=['PUT'])
@token_required
def update_headcount_target(user, target_id):
    """تحديث هدف الاستيعاب"""
    if not user.is_super_admin():
        return jsonify({'message': 'غير مصرح'}), 403

    target = HeadcountTarget.query.get_or_404(target_id)
    data = request.get_json()

    if 'target_count' in data:
        target.target_count = int(data['target_count'])
    if 'warning_threshold' in data:
        target.warning_threshold = int(data['warning_threshold'])
    if 'notes' in data:
        target.notes = data['notes']
    if 'branch_id' in data:
        target.branch_id = data['branch_id']
    if 'department_id' in data:
        target.department_id = data['department_id']

    from datetime import datetime
    target.updated_at = datetime.now()
    db.session.commit()
    return jsonify(target.to_dict()), 200


@recruitment_bp.route('/headcount-targets/<int:target_id>', methods=['DELETE'])
@token_required
def delete_headcount_target(user, target_id):
    """حذف هدف الاستيعاب"""
    if not user.is_super_admin():
        return jsonify({'message': 'غير مصرح'}), 403

    target = HeadcountTarget.query.get_or_404(target_id)
    db.session.delete(target)
    db.session.commit()
    return jsonify({'message': 'تم الحذف بنجاح'}), 200


@recruitment_bp.route('/headcount-targets/status', methods=['GET'])
@token_required
def headcount_status_route(user):
    """حالة كل هدف مع البيانات الحية"""
    result = get_headcount_status()
    return jsonify(result), 200


@recruitment_bp.route('/headcount-targets/check-all', methods=['POST'])
@token_required
def check_all_headcount_route(user):
    """تشغيل فحص الاستيعاب على جميع الأهداف"""
    if not user.is_super_admin():
        return jsonify({'message': 'غير مصرح'}), 403

    results = check_all_targets()
    return jsonify({'message': 'تم الفحص بنجاح', 'results': results}), 200


# ═══════════════════════════════════════════════════════════════════
# REPORTS & ANALYTICS
# ═══════════════════════════════════════════════════════════════════

@recruitment_bp.route('/reports/applications', methods=['GET'])
@token_required
def report_applications(user):
    """تقرير كامل لطلبات التوظيف مع كل الإجابات"""
    from app.recruitment.services.application_service import _get_field_map
    filters = {
        'status': request.args.get('status'),
        'branch_id': request.args.get('branch_id'),
        'department_id': request.args.get('department_id'),
        'date_from': request.args.get('date_from'),
        'date_to': request.args.get('date_to'),
    }
    filters = {k: v for k, v in filters.items() if v}

    from app.recruitment.reports import _get_applications, _build_answers_map, _build_experiences_map, STATUS_LABELS
    applications = _get_applications(filters)
    app_ids = [a.id for a in applications]
    answers_map = _build_answers_map(app_ids)
    experiences_map = _build_experiences_map(app_ids)

    field_map = _get_field_map()
    field_by_id = {f.id: f for f in field_map.values()}

    result = []
    for app in applications:
        ans = answers_map.get(app.id, {})
        exps = experiences_map.get(app.id, [])

        answers_formatted = {}
        for field_id, value in ans.items():
            field = field_by_id.get(field_id)
            if field:
                answers_formatted[field.field_key] = {
                    'label': field.label,
                    'value': value,
                    'field_type': field.field_type,
                }

        result.append({
            **app.to_dict(),
            'answers': answers_formatted,
            'experiences': [e.to_dict() for e in exps],
            'status_label': STATUS_LABELS.get(app.status, app.status),
        })

    return jsonify({'total': len(result), 'applications': result}), 200


@recruitment_bp.route('/reports/export', methods=['GET'])
@token_required
def export_report(user):
    """تصدير تقرير بصيغة Excel أو PDF"""
    fmt = request.args.get('format', 'excel').lower()
    filters = {
        'status': request.args.get('status'),
        'branch_id': request.args.get('branch_id'),
        'department_id': request.args.get('department_id'),
        'date_from': request.args.get('date_from'),
        'date_to': request.args.get('date_to'),
    }
    filters = {k: v for k, v in filters.items() if v}

    try:
        if fmt == 'excel':
            output = export_excel(filters)
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name='recruitment_report.xlsx'
            )
        elif fmt == 'pdf':
            output = export_pdf(filters)
            return send_file(
                output,
                mimetype='application/pdf',
                as_attachment=True,
                download_name='recruitment_report.pdf'
            )
        else:
            return jsonify({'message': "الصيغة غير مدعومة. استخدم 'excel' أو 'pdf'"}), 400

    except RuntimeError as e:
        return jsonify({'message': str(e)}), 500


@recruitment_bp.route('/analytics/funnel', methods=['GET'])
@token_required
def analytics_funnel(user):
    """تحليل مسار التوظيف - عدد الطلبات حسب الحالة"""
    from app import db

    args = request.args
    query = RecruitmentApplication.query

    if args.get('branch_id'):
        query = query.filter(RecruitmentApplication.branch_id == int(args['branch_id']))
    if args.get('department_id'):
        query = query.filter(RecruitmentApplication.department_id == int(args['department_id']))
    if args.get('date_from'):
        from datetime import datetime
        try:
            query = query.filter(
                RecruitmentApplication.created_at >= datetime.strptime(args['date_from'], '%Y-%m-%d')
            )
        except ValueError:
            pass
    if args.get('date_to'):
        from datetime import datetime
        try:
            query = query.filter(
                RecruitmentApplication.created_at <= datetime.strptime(args['date_to'], '%Y-%m-%d')
            )
        except ValueError:
            pass

    funnel = {}
    for status in ALLOWED_STATUSES:
        funnel[status] = query.filter(RecruitmentApplication.status == status).count()

    funnel['total'] = sum(funnel.values())
    return jsonify(funnel), 200


@recruitment_bp.route('/analytics/headcount-overview', methods=['GET'])
@token_required
def analytics_headcount_overview(user):
    """نظرة عامة على الاستيعاب"""
    result = get_headcount_status()
    return jsonify(result), 200
