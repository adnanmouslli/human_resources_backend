# app/recruitment/services/employee_mapper.py
# خدمة تحويل بيانات المتقدم إلى موظف عند القبول

from app import db
from app.models.employee import Employee
from app.recruitment.models import (
    RecruitmentApplication,
    RecruitmentApplicationAnswer,
    RecruitmentFormField,
)

# أعمدة مسموح بالربط بها في جدول الموظفين
VALID_EMPLOYEE_FIELDS = {
    'full_name', 'mobile_1', 'mobile_2', 'mobile_3',
    'residence', 'national_id', 'id_card_number',
    'place_of_birth', 'certificates', 'notes',
    'work_system', 'employee_type',
}


def validate_employee_field_mapping(field_name):
    """
    التحقق من أن اسم الحقل يُطابق عموداً موجوداً في جدول الموظفين.
    يعيد True إذا كان صالحاً.
    """
    return field_name in VALID_EMPLOYEE_FIELDS


def create_employee_from_application(application_id, hiring_decision_data):
    """
    إنشاء موظف تلقائياً من بيانات طلب التوظيف + بيانات قرار التعيين.

    hiring_decision_data يحتوي على:
        - fingerprint_id, salary, start_date, branch_id, department_id,
        - job_title_id (position), employee_type, work_system,
        - shift_id, profession_id

    المنطق:
    1. جمع كل الإجابات التي لها maps_to_employee_field
    2. دمجها مع بيانات قرار التعيين (القرار أولوية أعلى)
    3. التحقق من عدم وجود موظف مكرر (بالهاتف أو البصمة)
    4. إنشاء الموظف أو إعادة تحذير تكرار

    يعيد: ({ employee_id, warning }, error_message)
    """
    application = RecruitmentApplication.query.get(application_id)
    if not application:
        return None, "الطلب غير موجود"

    # جمع إجابات الحقول المرتبطة بعمود في جدول الموظفين
    employee_data = {}

    mapped_answers = (
        RecruitmentApplicationAnswer.query
        .join(RecruitmentFormField)
        .filter(
            RecruitmentApplicationAnswer.application_id == application_id,
            RecruitmentFormField.maps_to_employee_field.isnot(None),
        )
        .all()
    )

    for answer in mapped_answers:
        col = answer.field.maps_to_employee_field
        if col and validate_employee_field_mapping(col):
            if answer.value:
                employee_data[col] = answer.value

    # ──── دمج بيانات قرار التعيين (أولوية أعلى) ────

    # الحقول الأساسية من القرار (كلها اختيارية باستثناء branch/department/job_title/employee_type/work_system)
    employee_data['fingerprint_id'] = hiring_decision_data.get('fingerprint_id')  # قد تكون None
    employee_data['salary'] = hiring_decision_data.get('salary') or 0
    employee_data['date_of_joining'] = hiring_decision_data.get('start_date')
    employee_data['branch_id'] = hiring_decision_data.get('branch_id')
    employee_data['department_id'] = hiring_decision_data.get('department_id')
    employee_data['employee_type'] = hiring_decision_data.get('employee_type', 'permanent')
    employee_data['work_system'] = hiring_decision_data.get('work_system')

    # المسمى الوظيفي (position = FK to job_titles.id)
    employee_data['position'] = hiring_decision_data.get('job_title_id')

    # الوردية
    employee_data['shift_id'] = hiring_decision_data.get('shift_id')

    # المهنة (للمؤقتين)
    employee_data['profession_id'] = hiring_decision_data.get('profession_id')

    # full_name ضروري
    if not employee_data.get('full_name'):
        employee_data['full_name'] = application.applied_position or 'موظف جديد'

    # ──── التحقق من التكرار ────

    # التحقق من تكرار رقم البصمة (فقط إذا أُرسلت بصمة)
    fingerprint = employee_data.get('fingerprint_id')
    if fingerprint:
        existing_fp = Employee.query.filter_by(fingerprint_id=fingerprint).first()
        if existing_fp:
            return {'employee_id': existing_fp.id, 'warning': 'duplicate_fingerprint'}, None
    else:
        # البصمة مطلوبة في جدول الموظفين (NOT NULL).
        # في حال عدم إرسالها، يُحفظ قرار التعيين فقط دون إنشاء سجل موظف،
        # ويمكن استكمال البيانات لاحقاً.
        return {'employee_id': None, 'warning': 'pending_fingerprint'}, None

    # التحقق من تكرار رقم الهاتف
    phone = employee_data.get('mobile_1')
    if phone:
        existing_phone = Employee.query.filter(
            db.or_(
                Employee.mobile_1 == phone,
                Employee.mobile_2 == phone,
                Employee.mobile_3 == phone,
            )
        ).first()
        if existing_phone:
            return {'employee_id': existing_phone.id, 'warning': 'duplicate_phone'}, None

    # ──── إنشاء الموظف ────
    try:
        new_employee = Employee(
            fingerprint_id=employee_data.get('fingerprint_id'),
            full_name=employee_data.get('full_name', ''),
            employee_type=employee_data.get('employee_type', 'permanent'),
            branch_id=employee_data.get('branch_id'),
            department_id=employee_data.get('department_id'),
            position=employee_data.get('position') if employee_data.get('employee_type') == 'permanent' else None,
            profession_id=employee_data.get('profession_id') if employee_data.get('employee_type') == 'temporary' else None,
            salary=employee_data.get('salary', 0),
            work_system=employee_data.get('work_system'),
            shift_id=employee_data.get('shift_id'),
            date_of_joining=employee_data.get('date_of_joining'),
            mobile_1=employee_data.get('mobile_1'),
            mobile_2=employee_data.get('mobile_2'),
            mobile_3=employee_data.get('mobile_3'),
            residence=employee_data.get('residence'),
            national_id=employee_data.get('national_id'),
            id_card_number=employee_data.get('id_card_number'),
            place_of_birth=employee_data.get('place_of_birth'),
            certificates=employee_data.get('certificates'),
            notes=employee_data.get('notes'),
        )
        new_employee.auto_calculate_rates()
        db.session.add(new_employee)
        db.session.flush()
        return {'employee_id': new_employee.id, 'warning': None}, None

    except Exception as e:
        db.session.rollback()
        return None, str(e)
