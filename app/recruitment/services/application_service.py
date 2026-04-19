# app/recruitment/services/application_service.py
# خدمة إدارة طلبات التوظيف - CRUD + تخزين واسترجاع الإجابات

from datetime import datetime, date
from app import db
from app.recruitment.models import (
    RecruitmentApplication,
    RecruitmentApplicationAnswer,
    RecruitmentApplicationExperience,
    RecruitmentFormField,
    RecruitmentFormSection,
    ALLOWED_FIELD_TYPES,
)


# ─────────────────────────────────────────────────────────────────
# الدوال المساعدة
# ─────────────────────────────────────────────────────────────────

def _get_field_map():
    """إرجاع قاموس {field_key: RecruitmentFormField} لكل الحقول النشطة"""
    fields = RecruitmentFormField.query.filter_by(is_active=True).all()
    return {f.field_key: f for f in fields}


def _validate_answer_value(field, value):
    """
    التحقق من قيمة الإجابة حسب نوع الحقل.
    يعيد (True, None) إذا كانت صحيحة، أو (False, 'رسالة خطأ') إذا كانت خاطئة.
    """
    if value is None or str(value).strip() == '':
        return True, None  # القيم الفارغة مسموحة إذا لم يكن الحقل مطلوباً

    str_val = str(value).strip()

    if field.field_type == 'number':
        try:
            float(str_val)
        except ValueError:
            return False, f"الحقل '{field.label}' يجب أن يكون رقماً"

    elif field.field_type == 'date':
        try:
            datetime.strptime(str_val, '%Y-%m-%d')
        except ValueError:
            return False, f"الحقل '{field.label}' يجب أن يكون تاريخاً بصيغة YYYY-MM-DD"

    elif field.field_type == 'checkbox':
        if str_val not in ('0', '1', 'true', 'false', 'True', 'False'):
            return False, f"الحقل '{field.label}' يجب أن يكون 0 أو 1"

    return True, None


def _validate_required_fields(answers_dict, field_map):
    """التحقق من الحقول المطلوبة"""
    errors = []
    for field_key, field in field_map.items():
        if field.is_required and field.field_type != 'experience_group':
            val = answers_dict.get(field_key)
            if val is None or str(val).strip() == '':
                errors.append(f"الحقل '{field.label}' مطلوب")
    return errors


# ─────────────────────────────────────────────────────────────────
# تخزين الإجابات
# ─────────────────────────────────────────────────────────────────

def save_application_answers(application_id, answers_dict):
    """
    تخزين/تحديث إجابات طلب التوظيف.

    answers_dict: { field_key: value, ... }
    يتجاهل حقول experience_group تلقائياً.
    يعيد قائمة أخطاء التحقق (فارغة = ناجح).
    """
    field_map = _get_field_map()
    errors = []

    for field_key, value in answers_dict.items():
        field = field_map.get(field_key)
        if not field:
            continue  # تجاهل المفاتيح غير المعرَّفة

        if field.field_type == 'experience_group':
            continue  # يُعالَج بشكل منفصل

        # التحقق من القيمة
        valid, err = _validate_answer_value(field, value)
        if not valid:
            errors.append(err)
            continue

        # تحويل القيمة إلى نص
        str_value = str(value).strip() if value is not None and str(value).strip() != '' else None

        # upsert
        existing = RecruitmentApplicationAnswer.query.filter_by(
            application_id=application_id,
            field_id=field.id
        ).first()

        if existing:
            existing.value = str_value
        else:
            answer = RecruitmentApplicationAnswer(
                application_id=application_id,
                field_id=field.id,
                value=str_value
            )
            db.session.add(answer)

    return errors


def save_application_experiences(application_id, experiences_list):
    """
    تخزين خبرات المتقدم (يُحذف القديم ويُستبدل بالجديد).
    experiences_list: [ { company_name, company_field, position, duration,
                          hours_per_day, salary, reason_for_leaving }, ... ]
    """
    # حذف الخبرات القديمة
    RecruitmentApplicationExperience.query.filter_by(
        application_id=application_id
    ).delete()

    for idx, exp_data in enumerate(experiences_list, start=1):
        exp = RecruitmentApplicationExperience(
            application_id=application_id,
            experience_order=idx,
            company_name=exp_data.get('company_name'),
            company_field=exp_data.get('company_field'),
            position=exp_data.get('position'),
            duration=exp_data.get('duration'),
            hours_per_day=exp_data.get('hours_per_day'),
            salary=exp_data.get('salary'),
            reason_for_leaving=exp_data.get('reason_for_leaving'),
        )
        db.session.add(exp)


# ─────────────────────────────────────────────────────────────────
# إنشاء الطلب
# ─────────────────────────────────────────────────────────────────

def create_application(data, created_by_user_id):
    """
    إنشاء طلب توظيف جديد مع إجاباته وخبراته.

    يعيد (application, warning) حيث warning يكون 'duplicate_phone' أو None.
    """
    field_map = _get_field_map()

    answers_dict = data.get('answers', {})
    experiences_list = data.get('experiences', [])

    # التحقق من الحقول المطلوبة
    errors = _validate_required_fields(answers_dict, field_map)
    if errors:
        return None, {'errors': errors}

    # التحقق من التحقق من القيم
    for field_key, value in answers_dict.items():
        field = field_map.get(field_key)
        if field and field.field_type != 'experience_group':
            valid, err = _validate_answer_value(field, value)
            if not valid:
                return None, {'errors': [err]}

    # التحقق من تكرار رقم الهاتف
    warning = None
    phone_value = answers_dict.get('phone')
    if phone_value:
        phone_field = field_map.get('phone')
        if phone_field:
            existing_answer = RecruitmentApplicationAnswer.query.filter_by(
                field_id=phone_field.id,
                value=str(phone_value).strip()
            ).first()
            if existing_answer:
                warning = {
                    'type': 'duplicate_phone',
                    'existing_application_id': existing_answer.application_id
                }

    # إنشاء الطلب
    application = RecruitmentApplication(
        applied_position=data.get('applied_position', ''),
        branch_id=data.get('branch_id'),
        department_id=data.get('department_id'),
        status='new',
        created_by=created_by_user_id
    )
    db.session.add(application)
    db.session.flush()  # للحصول على application.id

    # تخزين الإجابات
    save_application_answers(application.id, answers_dict)

    # تخزين الخبرات
    if experiences_list:
        save_application_experiences(application.id, experiences_list)

    db.session.commit()
    return application, warning


# ─────────────────────────────────────────────────────────────────
# استرجاع الطلب مع تفاصيله الكاملة
# ─────────────────────────────────────────────────────────────────

def get_application_with_answers(application_id):
    """
    استرجاع الطلب مع كل إجاباته وخبراته وقرار التعيين.

    يعيد dict بالهيكل:
    {
        application: { ... },
        answers: { field_key: { label, value, field_type, section } },
        experiences: [ { ... }, ... ],
        hiring_decision: { ... } or null
    }
    """
    application = RecruitmentApplication.query.get(application_id)
    if not application:
        return None

    # إجابات منظَّمة حسب field_key
    answers = {}
    for answer in application.answers.join(RecruitmentFormField).order_by(
        RecruitmentFormField.display_order
    ).all():
        field = answer.field
        if field:
            answers[field.field_key] = {
                'label': field.label,
                'value': answer.value,
                'field_type': field.field_type,
                'section': field.section.name if field.section else None,
            }

    experiences = [e.to_dict() for e in application.experiences.all()]

    hiring_decision = application.hiring_decision.to_dict() if application.hiring_decision else None

    return {
        'application': application.to_dict(),
        'answers': answers,
        'experiences': experiences,
        'hiring_decision': hiring_decision,
    }


# ─────────────────────────────────────────────────────────────────
# تحديث الطلب
# ─────────────────────────────────────────────────────────────────

def update_application(application_id, data):
    """
    تحديث بيانات الطلب (غير مسموح إذا كان مقبولاً).
    يعيد (application, error_message).
    """
    application = RecruitmentApplication.query.get(application_id)
    if not application:
        return None, "الطلب غير موجود"

    if application.status == 'accepted':
        return None, "لا يمكن تعديل طلب مقبول"

    # تحديث الحقول الأساسية
    if 'applied_position' in data:
        application.applied_position = data['applied_position']
    if 'branch_id' in data:
        application.branch_id = data.get('branch_id')
    if 'department_id' in data:
        application.department_id = data.get('department_id')
    if 'evaluation_score' in data:
        application.evaluation_score = data.get('evaluation_score')

    application.updated_at = datetime.now()

    # تحديث الإجابات
    if 'answers' in data:
        field_map = _get_field_map()
        errors = []
        for field_key, value in data['answers'].items():
            field = field_map.get(field_key)
            if field and field.field_type != 'experience_group':
                valid, err = _validate_answer_value(field, value)
                if not valid:
                    errors.append(err)
        if errors:
            return None, '; '.join(errors)
        save_application_answers(application_id, data['answers'])

    # تحديث الخبرات
    if 'experiences' in data:
        save_application_experiences(application_id, data['experiences'])

    db.session.commit()
    return application, None


# ─────────────────────────────────────────────────────────────────
# قائمة الطلبات مع الفلترة والتقسيم إلى صفحات
# ─────────────────────────────────────────────────────────────────

def get_applications_list(filters=None, page=1, per_page=20):
    """
    استرجاع قائمة الطلبات مع دعم الفلترة الديناميكية والتقسيم إلى صفحات.

    filters: dict يمكن أن يحتوي على:
        - status
        - branch_id, department_id
        - dynamic field_key filters (is_searchable=True)
    """
    if filters is None:
        filters = {}

    query = RecruitmentApplication.query

    # فلتر الحالة
    if filters.get('status'):
        query = query.filter(RecruitmentApplication.status == filters['status'])

    # فلتر الفرع
    if filters.get('branch_id'):
        query = query.filter(RecruitmentApplication.branch_id == filters['branch_id'])

    # فلتر القسم
    if filters.get('department_id'):
        query = query.filter(RecruitmentApplication.department_id == filters['department_id'])

    # الفلاتر الديناميكية (الحقول القابلة للبحث)
    searchable_fields = RecruitmentFormField.query.filter_by(is_searchable=True, is_active=True).all()
    searchable_keys = {f.field_key: f for f in searchable_fields}

    for field_key, field in searchable_keys.items():
        if field_key in filters and filters[field_key]:
            search_val = str(filters[field_key]).strip()
            query = query.filter(
                RecruitmentApplication.answers.any(
                    db.and_(
                        RecruitmentApplicationAnswer.field_id == field.id,
                        RecruitmentApplicationAnswer.value.ilike(f'%{search_val}%')
                    )
                )
            )

    # ترتيب تنازلي حسب تاريخ الإنشاء
    query = query.order_by(RecruitmentApplication.created_at.desc())

    # تقسيم الصفحات
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # بناء النتائج مع أبرز إجابات الحقول القابلة للبحث
    results = []
    for app in pagination.items:
        app_dict = app.to_dict()

        # إضافة قيم الحقول القابلة للبحث للعرض السريع
        key_answers = {}
        for answer in app.answers.filter(
            RecruitmentApplicationAnswer.field_id.in_([f.id for f in searchable_fields])
        ).all():
            if answer.field:
                key_answers[answer.field.field_key] = answer.value
        app_dict['key_answers'] = key_answers
        results.append(app_dict)

    return {
        'items': results,
        'total': pagination.total,
        'pages': pagination.pages,
        'page': page,
        'per_page': per_page,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev,
    }


# ─────────────────────────────────────────────────────────────────
# حذف الطلب
# ─────────────────────────────────────────────────────────────────

def delete_application(application_id):
    """حذف طلب (cascade يحذف الإجابات والخبرات تلقائياً)"""
    application = RecruitmentApplication.query.get(application_id)
    if not application:
        return False, "الطلب غير موجود"

    db.session.delete(application)
    db.session.commit()
    return True, None
