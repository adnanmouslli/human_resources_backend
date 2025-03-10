from datetime import date
import os
from flask import Blueprint, current_app, request, jsonify
from app import db
from app.models import Attendance, Employee
from app.utils import token_required
from werkzeug.utils import secure_filename

employee_bp = Blueprint('employee', __name__)


# تحديد المجلدات المسموح بها لحفظ الملفات
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Create Employee
@employee_bp.route('/api/employees', methods=['POST'])
@token_required
def create_employee(user_id):
    # التحقق مما إذا كان الطلب يحتوي على بيانات متعددة الأجزاء (ملفات)
    if 'certificates' not in request.files and not request.is_json:
        return jsonify({'message': 'لا يوجد ملف شهادة'}), 400
    
    # الحصول على بيانات الموظف
    if request.is_json:
        data = request.get_json()
        certificate_file = None
    else:
        data = request.form.to_dict()
        certificate_file = request.files.get('certificates')
    
    # Validate required fields (adjust based on frontend inputs)
    required_fields = ['fingerprint_id', 'full_name', 'employee_type', 'work_system']
    missing_fields = [field for field in required_fields if field not in data or not data[field]]
    if missing_fields:
        return jsonify({'message': f'Missing fields: {", ".join(missing_fields)}'}), 400    
    
    # Additional validation based on employee type
    if data['employee_type'] == 'permanent' and 'position' not in data:
        return jsonify({'message': 'Position is required for permanent employees'}), 400
    elif data['employee_type'] == 'temporary' and 'profession' not in data:
        return jsonify({'message': 'Profession is required for temporary employees'}), 400
    
    # معالجة ملف الشهادة إذا تم تقديمه
    certificate_path = None
    if certificate_file and certificate_file.filename != '' and allowed_file(certificate_file.filename):
        # تأمين اسم الملف
        filename = secure_filename(certificate_file.filename)
        # إنشاء اسم ملف فريد باستخدام معرف البصمة
        unique_filename = f"{data['fingerprint_id']}_{filename}"
        
        # إنشاء مسار المجلد إذا لم يكن موجودًا
        certificates_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'certificates')
        if not os.path.exists(certificates_folder):
            os.makedirs(certificates_folder)
        
        # حفظ الملف
        file_path = os.path.join(certificates_folder, unique_filename)
        certificate_file.save(file_path)
        certificate_path = f"/uploads/certificates/{unique_filename}"

    try:


        birth_date_value = None
        if 'birth_date' in data and data['birth_date'] and data['birth_date'] != 'null':
            birth_date_value = data['birth_date']
            
        joining_date_value = None
        if 'date_of_joining' in data and data['date_of_joining'] and data['date_of_joining'] != 'null':
            joining_date_value = data['date_of_joining']

         # إضافة معالجة تواريخ التأمينات
        insurance_start_date_value = None
        if 'insurance_start_date' in data and data['insurance_start_date'] and data['insurance_start_date'] != 'null':
            insurance_start_date_value = data['insurance_start_date']
            
        insurance_end_date_value = None
        if 'insurance_end_date' in data and data['insurance_end_date'] and data['insurance_end_date'] != 'null':
            insurance_end_date_value = data['insurance_end_date']


        employee = Employee(
            fingerprint_id=data['fingerprint_id'],
            full_name=data['full_name'],
            employee_type=data['employee_type'],
            position=data.get('position') if data['employee_type'] == 'permanent' else None,
            profession_id=data.get('profession') if data['employee_type'] == 'temporary' else None,
            salary=data.get('salary', 0),
            advancePercentage=data.get('advancePercentage'),
            work_system=data['work_system'],
            date_of_birth=birth_date_value,  # استخدام القيمة المعالجة
            date_of_joining=joining_date_value,  # استخدام القيمة المعالجة
            certificates=certificate_path,  # حفظ مسار الملف بدلاً من النص
            place_of_birth=data.get('birth_place'),
            id_card_number=data.get('id_number'),
            national_id=data.get('national_id'),
            residence=data.get('residence'),
            mobile_1=data.get('phone1'),
            mobile_2=data.get('phone2'),
            mobile_3=data.get('phone3'),
            worker_agreement=data.get('agreement'),
            notes=data.get('notes'),
            shift_id=data.get('shift_id'),
            insurance_deduction=data.get('insurance_deduction', 0),
            allowances=data.get('allowances', 0),

            insurance_start_date=insurance_start_date_value,
            insurance_end_date=insurance_end_date_value,
        )
        db.session.add(employee)
        db.session.commit()

        return jsonify({'message': 'Employee created', 'employee': {
            'id': employee.id,
            'full_name': employee.full_name,
            'position': employee.position,
            'certificates': employee.certificates  # إرجاع مسار الملف في الاستجابة
        }}), 201

    except Exception as e:
        print(f"Error creating employee: {str(e)}")
        # طباعة البيانات المستلمة للمساعدة في تشخيص المشكلة
        print(f"Received data: {data}")     
        return jsonify({'message': 'Error creating employee', 'error': str(e)}), 500



# Get All Employees
@employee_bp.route('/api/employees', methods=['GET'])
@token_required
def get_all_employees(user_id):
    employees = Employee.query.all()
    return jsonify([
        {
            'id': emp.id,
            'fingerprint_id': emp.fingerprint_id,
            'full_name': emp.full_name,
            'employee_type': emp.employee_type,
            'position': emp.job_title.title_name if emp.job_title else None,
            'profession': emp.profession.name if emp.profession else None,
            'salary': float(emp.salary),
            'allowances': float(emp.allowances) if emp.allowances else 0,
            'insurance_deduction': float(emp.insurance_deduction) if emp.insurance_deduction else 0,
            'insurance_start_date': emp.insurance_start_date,
            'insurance_end_date': emp.insurance_end_date,
            'advancePercentage': float(emp.advancePercentage) if emp.advancePercentage else 0,
            'work_system': emp.work_system,
            'certificates': emp.certificates,
            'date_of_birth': emp.date_of_birth.isoformat() if emp.date_of_birth else None,
            'place_of_birth': emp.place_of_birth,
            'date_of_joining': emp.date_of_joining.isoformat() if emp.date_of_joining else None,
            'id_card_number': emp.id_card_number,
            'national_id': emp.national_id,
            'residence': emp.residence,
            'mobile_1': emp.mobile_1,
            'mobile_2': emp.mobile_2,
            'mobile_3': emp.mobile_3,
            'shift_id': emp.shift_id,
            'worker_agreement': emp.worker_agreement,
            'notes': emp.notes,
            'created_at': emp.created_at.isoformat(),
            'updated_at': emp.updated_at.isoformat()
        } for emp in employees
    ]), 200


# Get All EmployeesList
@employee_bp.route('/api/employees/list', methods=['GET'])
@token_required
def get_list_employees(user_id):
    employees = Employee.query.all()
    return jsonify([
        {
            'id': emp.id,
            'full_name': emp.full_name,
        } for emp in employees
    ]), 200

# Get Employee by ID
@employee_bp.route('/api/employees/<int:id>', methods=['GET'])
@token_required
def get_employee(user_id, id):
    employee = Employee.query.get(id)

    if not employee:
        return jsonify({'message': 'Employee not found'}), 404

    return jsonify({
        'id': employee.id,
        'fingerprint_id': employee.fingerprint_id,
        'full_name': employee.full_name,
        'position': employee.job_title.title_name if employee.job_title else None,  # اسم المسمى الوظيفي
        'salary': float(employee.salary),
        'allowances': float(employee.allowances) if employee.allowances else 0,
        'insurance_deduction': float(employee.insurance_deduction) if employee.insurance_deduction else 0,
        'advancePercentage': float(employee.advancePercentage) if employee.advancePercentage else 0,  # إضافة نسبة السلفة
        'work_system': employee.work_system,
        'certificates': employee.certificates,
        'date_of_birth': employee.date_of_birth.isoformat() if employee.date_of_birth else None,
        'place_of_birth': employee.place_of_birth,
        'id_card_number': employee.id_card_number,
        'national_id': employee.national_id,
        'residence': employee.residence,
        'mobile_1': employee.mobile_1,
        'mobile_2': employee.mobile_2,
        'mobile_3': employee.mobile_3,
        'worker_agreement': employee.worker_agreement,
        'notes': employee.notes,
        'shift_id': employee.shift_id,
        'profession_id': employee.profession_id,
        'date_of_joining': employee.date_of_joining.isoformat() if employee.date_of_joining else None,
        'created_at': employee.created_at.isoformat(),
        'updated_at': employee.updated_at.isoformat()
    }), 200


# Update Employee
@employee_bp.route('/api/employees/<int:id>', methods=['PUT'])
@token_required
def update_employee(user_id, id):
    employee = Employee.query.get(id)

    if not employee:
        return jsonify({'message': 'Employee not found'}), 404

    data = request.get_json()

    for key, value in data.items():
        if hasattr(employee, key):
            setattr(employee, key, value)

    db.session.commit()

    return jsonify({'message': 'Employee updated', 'employee': {
        'id': employee.id,
        'full_name': employee.full_name,
        'position': employee.position
    }}), 200


# Delete Employee
@employee_bp.route('/api/employees/<int:id>', methods=['DELETE'])
@token_required
def delete_employee(user_id, id):
    employee = Employee.query.get(id)

    if not employee:
        return jsonify({'message': 'Employee not found'}), 404

    db.session.delete(employee)
    db.session.commit()

    return jsonify({'message': 'Employee deleted'}), 200



@employee_bp.route('/api/employees/absent', methods=['GET'])
@token_required
def get_absent_employees(user_id):
    # الحصول على التاريخ الحالي أو التاريخ المحدد في الطلب
    selected_date = request.args.get('date', date.today().isoformat())  # دعم تحديد التاريخ كـ query param

    try:
        # استعلام لجلب الموظفين الذين ليس لديهم سجل حضور
        absent_employees = db.session.query(Employee).filter(
            ~Employee.id.in_(
                db.session.query(Attendance.empId).filter(
                    db.func.cast(Attendance.createdAt, db.Date) == selected_date
                )
            )
        ).all()

        # تحويل البيانات إلى JSON
        result = [
            {
                'id': emp.id,
                'full_name': emp.full_name,
                
            }
            for emp in absent_employees
        ]

        return jsonify(result), 200
    except Exception as e:
        return jsonify({'message': 'Error fetching absent employees', 'error': str(e)}), 500


@employee_bp.route('/api/employees/by-system/<system>', methods=['GET'])
@token_required
def get_employees_by_system(user_id, system):
    try:
        # فلترة الموظفين حسب نظام العمل
        employees = Employee.query.filter(
            Employee.work_system == system
        ).order_by(Employee.full_name).all()

        if not employees:
            return jsonify([]), 200

        return jsonify([{
            'id': str(emp.id),
            'full_name': emp.full_name,
        } for emp in employees]), 200

    except Exception as e:
        return jsonify({
            'message': 'حدث خطأ أثناء جلب بيانات الموظفين',
            'error': str(e)
        }), 500