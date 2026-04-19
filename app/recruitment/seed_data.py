# app/recruitment/seed_data.py
# البيانات الافتراضية لنموذج التوظيف - مستوحاة من ملف Excel المحلل
# يُنفَّذ مرة واحدة فقط عند كون الجداول فارغة

import json
from app import db
from app.recruitment.models import RecruitmentFormSection, RecruitmentFormField


def seed_default_form():
    """
    زرع البيانات الافتراضية للنموذج.
    يعيد False إذا كانت البيانات موجودة مسبقاً.
    """
    if RecruitmentFormSection.query.first():
        return False, "النموذج مُهيَّأ مسبقاً"

    sections_data = _build_sections_data()

    for section_data in sections_data:
        section = RecruitmentFormSection(
            name=section_data['name'],
            display_order=section_data['display_order'],
            is_active=True
        )
        db.session.add(section)
        db.session.flush()  # نحصل على section.id قبل الـ commit

        for order_idx, field_data in enumerate(section_data['fields'], start=1):
            options_json = json.dumps(field_data['options'], ensure_ascii=False) if field_data.get('options') else None
            field = RecruitmentFormField(
                section_id=section.id,
                field_key=field_data['field_key'],
                label=field_data['label'],
                field_type=field_data['field_type'],
                options=options_json,
                is_required=field_data.get('is_required', False),
                is_active=True,
                display_order=order_idx,
                maps_to_employee_field=field_data.get('maps_to_employee_field'),
                is_searchable=field_data.get('is_searchable', False),
                is_system_field=field_data.get('is_system_field', False),
            )
            db.session.add(field)

    db.session.commit()
    return True, "تم زرع بيانات النموذج بنجاح"


def _build_sections_data():
    return [
        # ────────────────────────────────────────────────
        # القسم 1: المعلومات الشخصية
        # ────────────────────────────────────────────────
        {
            'name': 'المعلومات الشخصية',
            'display_order': 1,
            'fields': [
                {
                    'field_key': 'full_name',
                    'label': 'الاسم',
                    'field_type': 'text',
                    'is_required': True,
                    'maps_to_employee_field': 'full_name',
                    'is_searchable': True,
                    'is_system_field': False,
                },
                {
                    'field_key': 'applied_position',
                    'label': 'تقديم على وظيفة',
                    'field_type': 'text',
                    'is_required': True,
                    'is_searchable': False,
                },
                {
                    'field_key': 'age',
                    'label': 'العمر',
                    'field_type': 'number',
                    'is_required': False,
                },
                {
                    'field_key': 'education_level',
                    'label': 'الدراسة',
                    'field_type': 'text',
                    'is_required': False,
                },
                {
                    'field_key': 'education_stage',
                    'label': 'المرحلة',
                    'field_type': 'select',
                    'options': ['متخرج', 'في الجامعة', 'أخر سنة', 'لا'],
                    'is_required': False,
                },
                {
                    'field_key': 'marital_status',
                    'label': 'الحالة الاجتماعية',
                    'field_type': 'select',
                    'options': ['أعزب', 'متزوج', 'مطلق', 'أرمل', 'خاطب'],
                    'is_required': False,
                },
                {
                    'field_key': 'military_status',
                    'label': 'الجيش',
                    'field_type': 'select',
                    'options': ['مؤدي', 'معفى', 'لم يتجند بعد', 'بدل', 'اعفاء'],
                    'is_required': False,
                    'is_searchable': True,
                },
                {
                    'field_key': 'military_reason',
                    'label': 'بسبب (الإعفاء)',
                    'field_type': 'text',
                    'is_required': False,
                },
                {
                    'field_key': 'residence_city',
                    'label': 'سكن بمصر',
                    'field_type': 'text',
                    'is_required': False,
                    'is_searchable': True,
                },
                {
                    'field_key': 'origin_city',
                    'label': 'المدينة الأصل',
                    'field_type': 'text',
                    'is_required': False,
                },
                {
                    'field_key': 'disability',
                    'label': 'عاهة',
                    'field_type': 'text',
                    'is_required': False,
                },
                {
                    'field_key': 'father_profession',
                    'label': 'مهنة والده',
                    'field_type': 'text',
                    'is_required': False,
                },
                {
                    'field_key': 'mother_profession',
                    'label': 'مهنة امه',
                    'field_type': 'text',
                    'is_required': False,
                },
                {
                    'field_key': 'siblings_profession',
                    'label': 'مهنة اخوه',
                    'field_type': 'text',
                    'is_required': False,
                },
                {
                    'field_key': 'phone',
                    'label': 'تليفون',
                    'field_type': 'phone',
                    'is_required': True,
                    'maps_to_employee_field': 'mobile_1',
                    'is_searchable': True,
                    'is_system_field': False,
                },
                {
                    'field_key': 'nationality',
                    'label': 'الجنسية',
                    'field_type': 'text',
                    'is_required': False,
                },
                {
                    'field_key': 'stability_in_country',
                    'label': 'استقرار بمصر',
                    'field_type': 'text',
                    'is_required': False,
                },
                {
                    'field_key': 'entry_to_country',
                    'label': 'دخول مصر',
                    'field_type': 'text',
                    'is_required': False,
                },
                {
                    'field_key': 'smoking',
                    'label': 'دخان',
                    'field_type': 'checkbox',
                    'is_required': False,
                },
                {
                    'field_key': 'availability',
                    'label': 'متفرغ',
                    'field_type': 'select',
                    'options': ['ملتزم', 'متفرغ', 'يوميات', 'بيدرس'],
                    'is_required': False,
                },
            ]
        },

        # ────────────────────────────────────────────────
        # القسم 2: المهارات والكفاءات
        # ────────────────────────────────────────────────
        {
            'name': 'المهارات والكفاءات',
            'display_order': 2,
            'fields': [
                {
                    'field_key': 'english_level',
                    'label': 'الإنجليزي',
                    'field_type': 'select',
                    'options': ['لا', 'مقبول', 'جيد', 'كويس', 'جدا', 'ممتاز'],
                    'is_required': False,
                },
                {
                    'field_key': 'computer_level',
                    'label': 'الكومبيوتر',
                    'field_type': 'select',
                    'options': ['لا', 'عادي', 'مقبول', 'جيد', 'كويس', 'ممتاز'],
                    'is_required': False,
                },
                {
                    'field_key': 'office_level',
                    'label': 'الأوفيس',
                    'field_type': 'select',
                    'options': ['لا', 'بسيط', 'عادي', 'جيد', 'ورد', 'جدا', 'ممتاز'],
                    'is_required': False,
                },
                {
                    'field_key': 'other_work',
                    'label': 'أعمال أخرى',
                    'field_type': 'textarea',
                    'is_required': False,
                },
                {
                    'field_key': 'general_experience',
                    'label': 'خبرة (ملخص)',
                    'field_type': 'textarea',
                    'is_required': False,
                },
                {
                    'field_key': 'teamwork',
                    'label': 'التعاون ومعاملة الفريق',
                    'field_type': 'select',
                    'options': ['لا', 'كويس', 'جيد', 'جدا', 'ممتاز', 'رائع', 'تمام', 'مرن في الصح'],
                    'is_required': False,
                },
                {
                    'field_key': 'hobbies',
                    'label': 'الهواية',
                    'field_type': 'text',
                    'is_required': False,
                },
                {
                    'field_key': 'course_1',
                    'label': 'كورس 1',
                    'field_type': 'text',
                    'is_required': False,
                },
                {
                    'field_key': 'course_2',
                    'label': 'كورس 2',
                    'field_type': 'text',
                    'is_required': False,
                },
                {
                    'field_key': 'course_source',
                    'label': 'من طرف',
                    'field_type': 'text',
                    'is_required': False,
                },
                {
                    'field_key': 'knows_someone',
                    'label': 'معرفة بشخص من الشركة',
                    'field_type': 'text',
                    'is_required': False,
                },
            ]
        },

        # ────────────────────────────────────────────────
        # القسم 3: الخبرات السابقة
        # ────────────────────────────────────────────────
        {
            'name': 'الخبرات السابقة',
            'display_order': 3,
            'fields': [
                {
                    'field_key': 'work_experiences',
                    'label': 'الخبرات السابقة',
                    'field_type': 'experience_group',
                    'is_required': False,
                },
            ]
        },

        # ────────────────────────────────────────────────
        # القسم 4: تقييم المقابلة
        # ────────────────────────────────────────────────
        {
            'name': 'تقييم المقابلة',
            'display_order': 4,
            'fields': [
                {
                    'field_key': 'interview_date_1',
                    'label': 'المقابلة (التاريخ)',
                    'field_type': 'date',
                    'is_required': False,
                },
                {
                    'field_key': 'interview_date_2',
                    'label': 'اللقاء الثاني (التاريخ)',
                    'field_type': 'date',
                    'is_required': False,
                },
                {
                    'field_key': 'interview_manager',
                    'label': 'مسؤول المقابلة',
                    'field_type': 'text',
                    'is_required': False,
                },
                {
                    'field_key': 'interview_location',
                    'label': 'مكان المقابلة',
                    'field_type': 'text',
                    'is_required': False,
                },
                {
                    'field_key': 'expected_role',
                    'label': 'اتوقعه في وظيفة',
                    'field_type': 'text',
                    'is_required': False,
                },
                {
                    'field_key': 'salary_expectation',
                    'label': 'توقعك للمرتب',
                    'field_type': 'text',
                    'is_required': False,
                },
                {
                    'field_key': 'commute_duration',
                    'label': 'مدة مواصلاته',
                    'field_type': 'text',
                    'is_required': False,
                },
                {
                    'field_key': 'commute_cost',
                    'label': 'قيمة مواصلاته',
                    'field_type': 'text',
                    'is_required': False,
                },
                {
                    'field_key': 'preferred_shift_start',
                    'label': 'يناسبه بداية الدوام',
                    'field_type': 'text',
                    'is_required': False,
                },
                {
                    'field_key': 'notes',
                    'label': 'ملاحظة',
                    'field_type': 'textarea',
                    'is_required': False,
                },
                {
                    'field_key': 'work_location',
                    'label': 'مكان العمل',
                    'field_type': 'text',
                    'is_required': False,
                },
                {
                    'field_key': 'interview_notes',
                    'label': 'ملاحظات المقابلة العامة',
                    'field_type': 'textarea',
                    'is_required': False,
                },
            ]
        },
    ]
