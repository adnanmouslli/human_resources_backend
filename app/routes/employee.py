from datetime import date
import os
from flask import Blueprint, current_app, request, jsonify
from werkzeug.utils import secure_filename

from app import db
from app.models.user import User
from app.models.branch import Branch
from app.models.department import Department

from app.utils import token_required

# ✅ استيرادات الموديلات بالشكل الصحيح
from app.models import Employee, Attendance, Advance, JobTitle, ProductionMonitoring, MonthlyAttendance, Branch , Department,BranchDepartment, Profession



employee_bp = Blueprint('employee', __name__)


# تحديد المجلدات المسموح بها لحفظ الملفات
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx', 'xlsx', 'xls'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


import pandas as pd
from werkzeug.utils import secure_filename

# تابع استيراد بيانات الموظفين من ملف Excel
@employee_bp.route('/api/employees/import', methods=['POST'])
@token_required
def import_employees(user_id):
    # Check if file is present in the request
    if 'file' not in request.files:
        return jsonify({'message': 'No file part in the request'}), 400
    
    file = request.files['file']
    
    # Check if a file was selected
    if file.filename == '':
        return jsonify({'message': 'No selected file'}), 400
    
    # Check file type
    if not allowed_file(file.filename):
        return jsonify({'message': 'Invalid file type. Only Excel files are allowed.'}), 400
    
    try:
        # Read Excel file using pandas
        df = pd.read_excel(file, dtype={
            'رقم البصمة': 'Int64',
            'الراتب الأساسي': float,
            'نسبة السلفة': float,
            'معرف الوردية': 'Int64',
            'تاريخ الميلاد': 'datetime64[ns]',
            'تاريخ بداية التأمين': 'datetime64[ns]',
            'تاريخ نهاية التأمين': 'datetime64[ns]'
        })
        
        # Rename columns to match Employee table fields
        df.rename(columns={
            'رقم البصمة': 'fingerprint_id',
            'الاسم الكامل': 'full_name',
            'نوع الموظف': 'employee_type',
            'المسمى الوظيفي': 'job_title_name',
            'المهنة': 'profession_name',
            'الشهادة': 'certificates',
            'الراتب الأساسي': 'salary',
            'نسبة السلفة': 'advancePercentage',
            'تاريخ الميلاد': 'date_of_birth',
            'مكان الميلاد': 'place_of_birth',
            'رقم الهوية الوطنية': 'national_id',
            'رقم هوية إضافي': 'id_card_number',
            'نوع العقد': 'contract_type',
            'العنوان': 'residence',
            'رقم الجوال الأساسي': 'mobile_1',
            'رقم جوال إضافي': 'mobile_2',
            'رقم الطوارئ': 'mobile_3',
            'نظام العمل': 'work_system',
            'معرف الوردية': 'shift_id',
            'قيمة التأمينات': 'insurance_deduction',
            'البدلات': 'allowances',
            'تاريخ بداية التأمين': 'insurance_start_date',
            'تاريخ نهاية التأمين': 'insurance_end_date',
            'ملاحظات': 'notes'
        }, inplace=True)
        
        # Check for required columns
        required_columns = ['fingerprint_id', 'full_name', 'employee_type']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return jsonify({'message': f'Missing required columns: {", ".join(missing_columns)}'}), 400
        
        # Print columns for debugging
        print("DataFrame columns:", df.columns.tolist())
        
        # Fill missing values based on data type
        numeric_cols = ['salary', 'advancePercentage', 'insurance_deduction', 'allowances']
        df[numeric_cols] = df[numeric_cols].fillna(0)
        nullable_int_cols = ['fingerprint_id', 'shift_id']
        df[nullable_int_cols] = df[nullable_int_cols].fillna(pd.NA).astype('Int64')

        # معالجة التواريخ بشكل آمن
        datetime_cols = ['date_of_birth', 'insurance_start_date', 'insurance_end_date']
        for col in datetime_cols:
            if col in df.columns:
                # تحويل التواريخ وتنظيف القيم غير الصالحة
                df[col] = pd.to_datetime(df[col], errors='coerce')
                
        string_cols = [
            'full_name', 'employee_type', 'job_title_name', 'profession_name',
            'certificates', 'place_of_birth', 'national_id', 'id_card_number',
            'contract_type', 'residence', 'mobile_1', 'mobile_2', 'mobile_3',
            'work_system', 'notes'
        ]
        df[string_cols] = df[string_cols].fillna('')

        # Print data after filling NaN
        print("DataFrame after filling NaN:", df.head())
        
        # Ensure numeric columns are properly converted
        df['fingerprint_id'] = pd.to_numeric(df['fingerprint_id'], errors='coerce').fillna(pd.NA).astype('Int64')
        df['salary'] = pd.to_numeric(df['salary'], errors='coerce').fillna(0)
        df['advancePercentage'] = pd.to_numeric(df['advancePercentage'], errors='coerce').fillna(0)
        df['shift_id'] = pd.to_numeric(df['shift_id'], errors='coerce').fillna(pd.NA).astype('Int64')
        df['insurance_deduction'] = pd.to_numeric(df['insurance_deduction'], errors='coerce').fillna(0)
        df['allowances'] = pd.to_numeric(df['allowances'], errors='coerce').fillna(0)
        
        # دالة مساعدة لمعالجة التواريخ
        def safe_date_convert(date_value):
            """تحويل آمن للتواريخ - إرجاع None للقيم غير الصالحة"""
            if pd.isna(date_value) or date_value is pd.NaT:
                return None
            try:
                if hasattr(date_value, 'date'):
                    return date_value.date()
                else:
                    return date_value
            except:
                return None
        
        # Convert to list of dictionaries
        employees_data = df.to_dict(orient='records')
        
        # ======================= جمع جميع المراجع المطلوبة مسبقاً =======================
        
        # جمع جميع job_titles وprofessions وshift_ids المطلوبة
        all_job_titles = set()
        all_professions = set()
        all_shift_ids = set()
        
        for data in employees_data:
            job_title = str(data.get('job_title_name', '')).strip()
            if job_title:
                all_job_titles.add(job_title)
            
            profession = str(data.get('profession_name', '')).strip()
            if profession:
                all_professions.add(profession)
            
            shift_id = data.get('shift_id')
            if pd.notna(shift_id) and shift_id not in ['', None]:
                try:
                    shift_id = int(float(shift_id))
                    if shift_id > 0:  # تجاهل الـ shift_id السالبة أو الصفر
                        all_shift_ids.add(shift_id)
                except (ValueError, TypeError):
                    pass
        
        print(f"Found job titles to process: {all_job_titles}")
        print(f"Found professions to process: {all_professions}")
        print(f"Found shift IDs to validate: {all_shift_ids}")
        
        # ======================= التحقق من صحة shift_ids =======================
        
        valid_shift_ids = set()
        if all_shift_ids:
            try:
                from app.models.shift import Shift  # استبدل بالمسار الصحيح لـ Shift model
                existing_shifts = Shift.query.filter(Shift.id.in_(all_shift_ids)).all()
                valid_shift_ids = {shift.id for shift in existing_shifts}
                
                invalid_shift_ids = all_shift_ids - valid_shift_ids
                if invalid_shift_ids:
                    print(f"WARNING: Invalid shift IDs found: {invalid_shift_ids}")
                    print(f"Valid shift IDs: {valid_shift_ids}")
                    
            except ImportError:
                print("Shift model not found - shift_id validation skipped")
                # إذا لم يوجد Shift model، اعتبر جميع shift_ids غير صالحة
                valid_shift_ids = set()
        
        # ======================= إنشاء أو جلب job_titles وprofessions =======================
        
        job_title_cache = {}
        profession_cache = {}
        
        # معالجة job_titles
        for job_title_name in all_job_titles:
            job_title_obj = JobTitle.query.filter_by(title_name=job_title_name).first()
            if not job_title_obj:
                job_title_obj = JobTitle(title_name=job_title_name)
                db.session.add(job_title_obj)
                db.session.flush()
            job_title_cache[job_title_name] = job_title_obj
        
        # معالجة professions
        for profession_name in all_professions:
            profession_obj = Profession.query.filter_by(name=profession_name).first()
            if not profession_obj:
                profession_obj = Profession(name=profession_name)
                db.session.add(profession_obj)
                db.session.flush()
            profession_cache[profession_name] = profession_obj
        
        print(f"Job title cache: {len(job_title_cache)} items")
        print(f"Profession cache: {len(profession_cache)} items")
        
        # ======================= معالجة كل سجل على حدة =======================
        
        processed_employees = []
        for data in employees_data:
            # معالجة التواريخ
            birth_date = safe_date_convert(data.get('date_of_birth'))
            insurance_start = safe_date_convert(data.get('insurance_start_date'))
            insurance_end = safe_date_convert(data.get('insurance_end_date'))
            
            # التحقق من صحة تواريخ التأمين
            if insurance_start and insurance_end:
                if insurance_start >= insurance_end:
                    print(f"تحذير: تواريخ تأمين غير صالحة للموظف {data.get('full_name', 'Unknown')}")
                    insurance_start = None
                    insurance_end = None
            elif insurance_start and not insurance_end:
                insurance_start = None
            elif insurance_end and not insurance_start:
                insurance_end = None
            
            processed_data = data.copy()
            processed_data['date_of_birth'] = birth_date
            processed_data['insurance_start_date'] = insurance_start
            processed_data['insurance_end_date'] = insurance_end
            
            processed_employees.append(processed_data)
        
        # ======================= إدراج البيانات =======================
        
        successful_imports = 0
        failed_imports = []
        
        for i, data in enumerate(processed_employees):
            try:
                # معالجة القيم الرقمية بشكل آمن
                def safe_int_convert(value):
                    if pd.isna(value) or value is None or value == '':
                        return None
                    try:
                        return int(float(value))
                    except (ValueError, TypeError):
                        return None
                
                def safe_float_convert(value, default=0.0):
                    if pd.isna(value) or value is None or value == '':
                        return default
                    try:
                        return float(value)
                    except (ValueError, TypeError):
                        return default
                
                # معالجة القيم
                fingerprint_id = safe_int_convert(data.get('fingerprint_id'))
                salary = safe_float_convert(data.get('salary'), 0)
                advance_percentage = safe_float_convert(data.get('advancePercentage'))
                insurance_deduction = safe_float_convert(data.get('insurance_deduction'), 0)
                allowances = safe_float_convert(data.get('allowances'), 0)
                
                # معالجة shift_id مع التحقق من الصحة
                shift_id = safe_int_convert(data.get('shift_id'))
                if shift_id and shift_id not in valid_shift_ids:
                    print(f"Row {i+1}: Invalid shift_id {shift_id}, setting to None")
                    shift_id = None
                
                # التحقق من القيم المطلوبة
                if not fingerprint_id:
                    failed_imports.append(f"Row {i+1}: Missing or invalid fingerprint_id")
                    continue
                
                full_name = str(data.get('full_name', '')).strip()
                if not full_name:
                    failed_imports.append(f"Row {i+1}: Missing full_name")
                    continue
                
                employee_type = str(data.get('employee_type', '')).strip()
                if not employee_type:
                    failed_imports.append(f"Row {i+1}: Missing employee_type")
                    continue
                
                # التحقق من وجود fingerprint_id مسبقاً
                existing_employee = Employee.query.filter_by(fingerprint_id=fingerprint_id).first()
                if existing_employee:
                    failed_imports.append(f"Row {i+1}: Fingerprint ID {fingerprint_id} already exists")
                    continue
                
                # الحصول على job_title وprofession من الـ cache
                job_title_name = str(data.get('job_title_name', '')).strip()
                job_title_obj = job_title_cache.get(job_title_name) if job_title_name else None
                
                profession_name = str(data.get('profession_name', '')).strip()
                profession_obj = profession_cache.get(profession_name) if profession_name else None
                
                # Create Employee object
                employee = Employee(
                    fingerprint_id=fingerprint_id,
                    full_name=full_name,
                    employee_type=employee_type,
                    position=job_title_obj.id if job_title_obj else None,
                    profession_id=profession_obj.id if profession_obj else None,
                    salary=salary,
                    advancePercentage=advance_percentage,
                    work_system=str(data.get('work_system', '')).strip() or None,
                    date_of_birth=data.get('date_of_birth'),
                    place_of_birth=str(data.get('place_of_birth', '')).strip() or None,
                    national_id=str(data.get('national_id', '')).strip() or None,
                    id_card_number=str(data.get('id_card_number', '')).strip() or None,
                    residence=str(data.get('residence', '')).strip() or None,
                    mobile_1=str(data.get('mobile_1', '')).strip() or None,
                    mobile_2=str(data.get('mobile_2', '')).strip() or None,
                    mobile_3=str(data.get('mobile_3', '')).strip() or None,
                    shift_id=shift_id,  # سيكون None إذا كان غير صالح
                    insurance_deduction=insurance_deduction,
                    allowances=allowances,
                    insurance_start_date=data.get('insurance_start_date'),
                    insurance_end_date=data.get('insurance_end_date'),
                    notes=str(data.get('notes', '')).strip() or None,
                    certificates=str(data.get('certificates', '')).strip() or None
                )
                
                db.session.add(employee)
                successful_imports += 1
                
            except Exception as e:
                failed_imports.append(f"Row {i+1}: {str(e)}")
                print(f"Error processing row {i+1}: {str(e)}")
                continue
        
        # Commit changes
        db.session.commit()
        
        response_message = f'Import completed: {successful_imports} employees imported successfully'
        if failed_imports:
            response_message += f', {len(failed_imports)} failed'
        
        return jsonify({
            'message': response_message,
            'successful': successful_imports,
            'failed': len(failed_imports),
            'errors': failed_imports[:10],  # عرض أول 10 أخطاء فقط
            'validation_info': {
                'total_shift_ids_found': len(all_shift_ids),
                'valid_shift_ids': list(valid_shift_ids),
                'invalid_shift_ids': list(all_shift_ids - valid_shift_ids) if all_shift_ids else [],
                'job_titles_created': len(job_title_cache),
                'professions_created': len(profession_cache)
            }
        }), 201
    
    except Exception as e:
        # Rollback changes on error
        db.session.rollback()
        print(f"Full error: {str(e)}")
        return jsonify({'message': 'Error importing employees', 'error': str(e)}), 500
    
@employee_bp.route('/api/employees', methods=['POST'])
@token_required
def create_employee(user_id):
    
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
        filename = secure_filename(certificate_file.filename)
        unique_filename = f"{data['fingerprint_id']}_{filename}"
        
        certificates_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'certificates')
        if not os.path.exists(certificates_folder):
            os.makedirs(certificates_folder)
        
        file_path = os.path.join(certificates_folder, unique_filename)
        certificate_file.save(file_path)
        certificate_path = f"/uploads/certificates/{unique_filename}"

    try:
        # دالة مساعدة لمعالجة التواريخ
        def process_date(date_value):
            if not date_value or date_value == 'null' or date_value == '' or str(date_value).lower() == 'nat':
                return None
            try:
                if isinstance(date_value, str):
                    from datetime import datetime
                    date_formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y-%m-%d %H:%M:%S']
                    for fmt in date_formats:
                        try:
                            return datetime.strptime(date_value, fmt).date()
                        except ValueError:
                            continue
                    return None
                elif hasattr(date_value, 'date'):
                    return date_value.date() if hasattr(date_value, 'date') else date_value
                else:
                    return None
            except:
                return None

        birth_date_value = process_date(data.get('birth_date'))
        joining_date_value = process_date(data.get('date_of_joining'))
        insurance_start_date_value = process_date(data.get('insurance_start_date'))
        insurance_end_date_value = process_date(data.get('insurance_end_date'))

        # التحقق من صحة تواريخ التأمين
        if insurance_start_date_value and insurance_end_date_value:
            if insurance_start_date_value > insurance_end_date_value:
                return jsonify({'message': 'تاريخ بداية التأمين يجب أن يكون قبل تاريخ النهاية'}), 400

        # تحويل البيانات الإضافية للفرع والقسم
        branch_id = None
        if 'branch_id' in data and data['branch_id'] and data['branch_id'] != 'null' and str(data['branch_id']).strip():
            try:
                branch_id = int(data['branch_id'])
            except (ValueError, TypeError):
                branch_id = None
            
        department_id = None
        if 'department_id' in data and data['department_id'] and data['department_id'] != 'null' and str(data['department_id']).strip():
            try:
                department_id = int(data['department_id'])
            except (ValueError, TypeError):
                department_id = None
        
        # التحقق من مدى صلاحية الفرع والقسم
        if branch_id:
            branch = Branch.query.get(branch_id)
            if not branch:
                return jsonify({'message': 'الفرع غير موجود'}), 400
        
        if department_id:
            department = Department.query.get(department_id)
            if not department:
                return jsonify({'message': 'القسم غير موجود'}), 400
            
            if branch_id:
                branch_dept_rel = BranchDepartment.query.filter_by(
                    branch_id=branch_id, department_id=department_id
                ).first()
                if not branch_dept_rel:
                    return jsonify({'message': 'القسم غير متوفر في الفرع المحدد'}), 400
        
        # معالجة القيم الرقمية
        def process_numeric(value, default=0):
            if not value or value == 'null' or value == '':
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default

        def process_integer(value, default=None):
            if not value or value == 'null' or value == '':
                return default
            try:
                return int(value)
            except (ValueError, TypeError):
                return default

        salary_value = process_numeric(data.get('salary'), 0)
        advance_percentage = process_numeric(data.get('advancePercentage'))
        insurance_deduction = process_numeric(data.get('insurance_deduction'), 0)
        allowances = process_numeric(data.get('allowances'), 0)
        
        # معالجة الحقول الجديدة
        overtime_multiplier = process_numeric(data.get('overtime_multiplier'), 1.5)
        daily_rate = process_numeric(data.get('daily_rate'), None) if data.get('daily_rate') else None
        hourly_rate = process_numeric(data.get('hourly_rate'), None) if data.get('hourly_rate') else None
        
        shift_id = process_integer(data.get('shift_id'))
        profession_id = process_integer(data.get('profession')) if data['employee_type'] == 'temporary' else None

        employee = Employee(
            fingerprint_id=data['fingerprint_id'],
            full_name=data['full_name'],
            employee_type=data['employee_type'],
            position=data.get('position') if data['employee_type'] == 'permanent' else None,
            profession_id=profession_id,
            salary=salary_value,
            advancePercentage=advance_percentage,
            work_system=data['work_system'],
            date_of_birth=birth_date_value,
            date_of_joining=joining_date_value,
            certificates=certificate_path,
            place_of_birth=data.get('birth_place'),
            id_card_number=data.get('id_number'),
            national_id=data.get('national_id'),
            residence=data.get('residence'),
            mobile_1=data.get('phone1'),
            mobile_2=data.get('phone2'),
            mobile_3=data.get('phone3'),
            worker_agreement=data.get('agreement'),
            notes=data.get('notes'),
            shift_id=shift_id,
            insurance_deduction=insurance_deduction,
            allowances=allowances,
            insurance_start_date=insurance_start_date_value,
            insurance_end_date=insurance_end_date_value,
            branch_id=branch_id,
            department_id=department_id,
            # الحقول الجديدة
            overtime_multiplier=overtime_multiplier,
            daily_rate=daily_rate,
            hourly_rate=hourly_rate,
        )
        
        # إذا لم يتم تحديد سعر اليوم أو الساعة، احسبهما تلقائياً
        if not daily_rate or not hourly_rate:
            if employee.auto_calculate_rates():
                # تم الحساب التلقائي بنجاح
                pass
        
        db.session.add(employee)
        db.session.commit()

        return jsonify({'message': 'Employee created', 'employee': {
            'id': employee.id,
            'full_name': employee.full_name,
            'position': employee.position,
            'certificates': employee.certificates,
            'branch_id': employee.branch_id,
            'department_id': employee.department_id,
            'overtime_multiplier': float(employee.overtime_multiplier) if employee.overtime_multiplier else 1.5,
            'daily_rate': float(employee.daily_rate) if employee.daily_rate else None,
            'hourly_rate': float(employee.hourly_rate) if employee.hourly_rate else None,
        }}), 201

    except Exception as e:
        db.session.rollback()
        print(f"Error creating employee: {str(e)}")
        print(f"Received data: {data}")     
        return jsonify({'message': 'Error creating employee', 'error': str(e)}), 500


@employee_bp.route('/api/employees', methods=['GET'])
@token_required
def get_all_employees(user):
    
    user = user.query.get(user.id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    accessible_employees = user.get_accessible_employees()
    result = []
    
    for emp in accessible_employees:
        branch_name = emp.branch.name if emp.branch else None
        department_name = emp.department.name if emp.department else None

        # الحصول على المسمى الوظيفي
        job_title_name = None
        if emp.position:
            from app.models.job_title import JobTitle
            job_title = JobTitle.query.get(emp.position)
            if job_title:
                job_title_name = job_title.title_name

        # الحصول على المهنة
        profession_name = None
        if emp.profession_id:
            from app.models.profession import Profession
            profession = Profession.query.get(emp.profession_id)
            if profession:
                profession_name = profession.name

        is_dept_head = emp.has_user_account() and emp.user_account.is_department_head()

        result.append({
            'id': emp.id,
            'fingerprint_id': emp.fingerprint_id,
            'full_name': emp.full_name,
            'employee_type': emp.employee_type,
            'position': job_title_name,
            'profession': profession_name,
            'salary': float(emp.salary) if emp.salary else 0,
            'allowances': float(emp.allowances) if emp.allowances else 0,
            'insurance_deduction': float(emp.insurance_deduction) if emp.insurance_deduction else 0,
            'insurance_start_date': emp.insurance_start_date.isoformat() if emp.insurance_start_date else None,
            'insurance_end_date': emp.insurance_end_date.isoformat() if emp.insurance_end_date else None,
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
            'updated_at': emp.updated_at.isoformat(),
            'branch_id': emp.branch_id,
            'branch_name': branch_name,
            'department_id': emp.department_id,
            'department_name': department_name,
            'is_department_head': is_dept_head,
            # الحقول الجديدة
            'overtime_multiplier': float(emp.overtime_multiplier) if emp.overtime_multiplier else 1.5,
            'daily_rate': float(emp.daily_rate) if emp.daily_rate else None,
            'hourly_rate': float(emp.hourly_rate) if emp.hourly_rate else None,
        })
    
    return jsonify(result), 200



# Get All EmployeesList
@employee_bp.route('/api/employees/list', methods=['GET'])
@token_required
def get_list_employees(user):
    from app.models.user import User
    from app.models.employee import Employee
    from app.models.department import Department
    from app.models.branch import Branch

    # جلب بيانات المستخدم
    user = User.query.get(user.id)
    if not user:
        return jsonify({'message': 'المستخدم غير موجود'}), 404

    employees = []

    if user.is_super_admin():
        # سوبر أدمن يرى كل الموظفين
        employees = Employee.query.all()

    elif user.is_branch_head() or user.is_branch_deputy():
        # رئيس الفرع أو نائبه -> جلب كل الموظفين في الفرع + رؤساء الأقسام ونوابهم في الفرع
        if not user.branch_id:
            return jsonify([]), 200

        # جلب موظفي الفرع مباشرة
        branch_employees = Employee.query.filter_by(branch_id=user.branch_id).all()

        # جلب رؤساء الأقسام ونوابهم في نفس الفرع
        department_heads_and_deputies = Employee.query.join(Department).filter(
            Department.branch_id == user.branch_id,
            Employee.user_account.has(User.user_type.in_(['department_head', 'department_deputy']))
        ).all()

        # دمج النتائج وعدم تكرار الموظف
        employees = list({e.id: e for e in (branch_employees + department_heads_and_deputies)}.values())

    elif user.is_department_head() or user.is_department_deputy():
        # رئيس القسم أو نائبه -> جلب موظفي القسم فقط
        if not user.department_id:
            return jsonify([]), 200

        employees = Employee.query.filter_by(department_id=user.department_id).all()

    elif user.user_type == 'employee':
        # موظف عادي -> يرى نفسه فقط
        if user.employee:
            employees = [user.employee]
        else:
            employees = []

    else:
        return jsonify([]), 200

    # تحويل البيانات إلى JSON
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

    branch_name = None
    if employee.branch_id:
        branch = Branch.query.get(employee.branch_id)
        if branch:
            branch_name = branch.name
    
    department_name = None
    if employee.department_id:
        department = Department.query.get(employee.department_id)
        if department:
            department_name = department.name

    return jsonify({
        'id': employee.id,
        'fingerprint_id': employee.fingerprint_id,
        'full_name': employee.full_name,
        'position': employee.job_title.title_name if employee.job_title else None,
        'salary': float(employee.salary),
        'allowances': float(employee.allowances) if employee.allowances else 0,
        'insurance_deduction': float(employee.insurance_deduction) if employee.insurance_deduction else 0,
        'advancePercentage': float(employee.advancePercentage) if employee.advancePercentage else 0,
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
        'updated_at': employee.updated_at.isoformat(),
        'branch_id': employee.branch_id,
        'branch_name': branch_name,
        'department_id': employee.department_id,
        'department_name': department_name,
        'is_department_head': employee.is_department_head,
        # الحقول الجديدة
        'overtime_multiplier': float(employee.overtime_multiplier) if employee.overtime_multiplier else 1.5,
        'daily_rate': float(employee.daily_rate) if employee.daily_rate else None,
        'hourly_rate': float(employee.hourly_rate) if employee.hourly_rate else None,
    }), 200


# Update Employee
# تحديث دالة update_employee في الباك إند

@employee_bp.route('/api/employees/<int:id>', methods=['PUT'])
@token_required
def update_employee(user_id, id):
    employee = Employee.query.get(id)
    
    if not employee:
        return jsonify({'message': 'Employee not found'}), 404

    data = request.get_json()
    
    try:
        # دالة مساعدة لمعالجة التواريخ
        def process_date(date_value):
            if not date_value or date_value == 'null' or date_value == '':
                return None
            try:
                if isinstance(date_value, str):
                    from datetime import datetime
                    date_formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']
                    for fmt in date_formats:
                        try:
                            return datetime.strptime(date_value, fmt).date()
                        except ValueError:
                            continue
                    return None
                return date_value
            except:
                return None

        # دالة مساعدة لمعالجة الأرقام
        def process_numeric(value, default=None):
            if value is None or value == '' or value == 'null':
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default

        def process_integer(value, default=None):
            if value is None or value == '' or value == 'null':
                return default
            try:
                return int(value)
            except (ValueError, TypeError):
                return default

        # تحديث الحقول الأساسية
        if 'fingerprint_id' in data:
            employee.fingerprint_id = data['fingerprint_id']
        
        if 'full_name' in data:
            employee.full_name = data['full_name']
        
        if 'employee_type' in data:
            employee.employee_type = data['employee_type']
        
        if 'position' in data:
            employee.position = data['position']
        
        if 'mobile_1' in data:
            employee.mobile_1 = data['mobile_1']
        
        if 'national_id' in data:
            employee.national_id = data['national_id']
        
        if 'residence' in data:
            employee.residence = data['residence']
        
        # معالجة الحقول المالية للموظفين الدائمين
        if employee.employee_type == 'permanent':
            if 'salary' in data:
                employee.salary = process_numeric(data['salary'], 0)
            
            if 'allowances' in data:
                employee.allowances = process_numeric(data['allowances'], 0)
            
            if 'advancePercentage' in data:
                employee.advancePercentage = process_numeric(data['advancePercentage'], 0)
            
            # معالجة الحقول الجديدة للإضافي
            if 'overtime_multiplier' in data:
                employee.overtime_multiplier = process_numeric(data['overtime_multiplier'], 1.5)
            
            if 'daily_rate' in data:
                employee.daily_rate = process_numeric(data['daily_rate'])
            
            if 'hourly_rate' in data:
                employee.hourly_rate = process_numeric(data['hourly_rate'])
            
            # معالجة التواريخ
            if 'date_of_birth' in data:
                employee.date_of_birth = process_date(data['date_of_birth'])
            
            if 'place_of_birth' in data:
                employee.place_of_birth = data['place_of_birth']

        # معالجة نظام العمل والوردية
        if 'work_system' in data:
            employee.work_system = data['work_system']
            
            # إذا كان نظام العمل وردية، تحديث الوردية
            if data['work_system'] == 'shift' and 'shift' in data:
                employee.shift_id = process_integer(data['shift'])
            elif data['work_system'] != 'shift':
                # إذا تم تغيير نظام العمل من وردية إلى شيء آخر، إزالة الوردية
                employee.shift_id = None

        # حساب تلقائي للمعدلات إذا لم يتم تحديدها
        if employee.employee_type == 'permanent' and employee.salary:
            # حساب سعر اليوم إذا لم يتم تحديده
            if not employee.daily_rate:
                employee.daily_rate = round(employee.salary / 30, 2)
            
            # حساب سعر الساعة إذا لم يتم تحديده
            if not employee.hourly_rate and employee.daily_rate:
                employee.hourly_rate = round(employee.daily_rate / 8, 2)

        db.session.commit()

        # إرجاع البيانات المحدثة
        return jsonify({
            'message': 'Employee updated successfully',
            'employee': {
                'id': employee.id,
                'fingerprint_id': employee.fingerprint_id,
                'full_name': employee.full_name,
                'employee_type': employee.employee_type,
                'position': employee.position,
                'salary': float(employee.salary) if employee.salary else 0,
                'allowances': float(employee.allowances) if employee.allowances else 0,
                'advancePercentage': float(employee.advancePercentage) if employee.advancePercentage else 0,
                'overtime_multiplier': float(employee.overtime_multiplier) if employee.overtime_multiplier else 1.5,
                'daily_rate': float(employee.daily_rate) if employee.daily_rate else None,
                'hourly_rate': float(employee.hourly_rate) if employee.hourly_rate else None,
                'work_system': employee.work_system,
                'shift_id': employee.shift_id,
                'mobile_1': employee.mobile_1,
                'national_id': employee.national_id,
                'residence': employee.residence,
                'date_of_birth': employee.date_of_birth.isoformat() if employee.date_of_birth else None,
                'place_of_birth': employee.place_of_birth
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"Error updating employee: {str(e)}")
        return jsonify({
            'message': 'Error updating employee',
            'error': str(e)
        }), 500
    
# Delete Employee
@employee_bp.route('/api/employees/<int:emp_id>', methods=['DELETE'])
@token_required
def delete_employee(user_id, emp_id):
    employee = Employee.query.get(emp_id)
    
    if not employee:
        return jsonify({'message': 'Employee not found'}), 404

    # التحقق من الارتباطات
    has_attendances = Attendance.query.filter_by(empId=emp_id).first()
    has_advances = Advance.query.filter_by(employee_id=emp_id).first()
    has_production = ProductionMonitoring.query.filter_by(employee_id=emp_id).first()
    has_monthly_attendance = MonthlyAttendance.query.filter_by(employee_id=emp_id).first()


    if has_attendances or has_advances or has_production or has_monthly_attendance:
        return jsonify({
            'status': 400,
            'message': 'لا يمكن حذف هذا الموظف بسبب وجود سجلات مرتبطة.'
        }), 200

    # # التحقق مما إذا كان الموظف رئيس قسم وإزالة العلاقة
    # if employee.is_department_head and employee.department_id:
    #     department = Department.query.get(employee.department_id)
    #     if department and department.head_id == emp_id:
    #         department.head_id = None

    # إذا لم توجد علاقات، قم بالحذف
    db.session.delete(employee)
    db.session.commit()
    return jsonify({
        'status': 200,
        'message': 'Employee deleted successfully'
    }), 200


@employee_bp.route('/api/employees/absent', methods=['GET'])
@token_required
def get_absent_employees(current_user):
    # الحصول على التاريخ الحالي أو التاريخ المحدد في الطلب
    selected_date = request.args.get('date', date.today().isoformat())  # دعم تحديد التاريخ كـ query param

    try:
        
        # الحصول على الموظفين الذين يمكن للمستخدم الوصول إليهم حسب صلاحياته
        accessible_employees = current_user.get_accessible_employees()
        accessible_employee_ids = [emp.id for emp in accessible_employees]

        if not accessible_employee_ids:
            return jsonify({
                'message': 'لا توجد موظفين يمكن الوصول إليهم لهذا المستخدم',
                'user_type': current_user.user_type,
                'accessible_count': 0
            }), 200

        # استعلام لجلب الموظفين الغائبين من الموظفين المسموح لهم فقط
        # مع استثناء الموظفين في إجازة أو عطلة
        absent_employees = db.session.query(Employee).filter(
            Employee.id.in_(accessible_employee_ids),  # فلترة حسب الصلاحيات
            ~Employee.id.in_(
                db.session.query(Attendance.empId).filter(
                    db.func.cast(Attendance.createdAt, db.Date) == selected_date
                )
            )
        ).all()

        # فلترة إضافية لاستثناء الموظفين في إجازة أو عطلة
        from app.models.holiday import Holiday
        from app.models.leave import Leave
        from datetime import datetime
        
        selected_date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
        
        # التحقق من العطل العامة
        general_holidays = Holiday.query.filter(
            Holiday.is_active == True,
            Holiday.branch_id.is_(None),
            Holiday.department_id.is_(None),
            Holiday.date == selected_date_obj
        ).all()
        
        is_general_holiday = len(general_holidays) > 0
        
        # فلترة الموظفين الغائبين
        filtered_absent_employees = []
        
        for emp in absent_employees:
            # التحقق من الإجازات الشخصية
            personal_leave = Leave.query.filter(
                Leave.employee_id == emp.id,
                Leave.start_date <= selected_date_obj,
                Leave.end_date >= selected_date_obj,
                Leave.status == 'approved'
            ).first()
            
            # التحقق من العطل الخاصة بالفرع أو القسم
            branch_holiday = None
            department_holiday = None
            
            if emp.branch_id:
                branch_holiday = Holiday.query.filter(
                    Holiday.is_active == True,
                    Holiday.branch_id == emp.branch_id,
                    Holiday.date == selected_date_obj
                ).first()
            
            if emp.department_id:
                department_holiday = Holiday.query.filter(
                    Holiday.is_active == True,
                    Holiday.department_id == emp.department_id,
                    Holiday.date == selected_date_obj
                ).first()
            
            # إذا كان الموظف في إجازة أو عطلة، لا نعتبره غائب
            if personal_leave or is_general_holiday or branch_holiday or department_holiday:
                continue
                
            filtered_absent_employees.append(emp)

        result = [
            {
                'id': emp.id,
                'full_name': emp.full_name,
                
            }
            for emp in filtered_absent_employees
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
    


@employee_bp.route('/api/employees/classify_employees', methods=['GET'])
@token_required
def classify_employees(current_user):
    user = User.query.get(current_user.id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    # جلب جميع الموظفين الذين يمكن للمستخدم الوصول إليهم
    accessible_employees = user.get_accessible_employees()

    # التصنيفات الثلاثة
    employees_with_dept_branch = []
    employees_without_dept_branch = []
    manager_employees = []

    for emp in accessible_employees:
        branch_name = emp.branch.name if emp.branch else None
        department_name = emp.department.name if emp.department else None

        # تحديد إن كان موظف مرتبطًا بقسم وفرع
        has_dept_branch = bool(emp.department_id or emp.branch_id)

        # الحصول على المسمى الوظيفي
        job_title_name = None
        if emp.position:
            from app.models.job_title import JobTitle
            job_title = JobTitle.query.get(emp.position)
            if job_title:
                job_title_name = job_title.title_name

        # الحصول على المهنة
        profession_name = None
        if emp.profession_id:
            from app.models.profession import Profession
            profession = Profession.query.get(emp.profession_id)
            if profession:
                profession_name = profession.name

        # تحديد إذا كان مدير (رئيس/نائب رئيس فرع أو قسم)
        is_manager = False
        if emp.has_user_account():
            user_type = emp.user_account.user_type
            is_manager = user_type in ['branch_head', 'branch_deputy', 'department_head', 'department_deputy']

        employee_data = {
            'id': emp.id,
            'fingerprint_id': emp.fingerprint_id,
            'full_name': emp.full_name,
            'employee_type': emp.employee_type,
            'position': job_title_name,
            'profession': profession_name,
            'salary': float(emp.salary) if emp.salary else 0,
            'allowances': float(emp.allowances) if emp.allowances else 0,
            'insurance_deduction': float(emp.insurance_deduction) if emp.insurance_deduction else 0,
            'insurance_start_date': emp.insurance_start_date.isoformat() if emp.insurance_start_date else None,
            'insurance_end_date': emp.insurance_end_date.isoformat() if emp.insurance_end_date else None,
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
            'updated_at': emp.updated_at.isoformat(),
            'branch_id': emp.branch_id,
            'branch_name': branch_name,
            'department_id': emp.department_id,
            'department_name': department_name,
            'is_manager': is_manager
        }

        if is_manager:
            manager_employees.append(employee_data)
        elif has_dept_branch:
            employees_with_dept_branch.append(employee_data)
        else:
            employees_without_dept_branch.append(employee_data)

    response = {
        "with_dept_branch": employees_with_dept_branch,
        "without_dept_branch": employees_without_dept_branch,
        "manager_employees": manager_employees
    }

    return jsonify(response), 200



@employee_bp.route('/api/employees/<int:emp_id>/assignment', methods=['DELETE'])
@token_required
def remove_employee_assignment(current_user, emp_id):
    """إزالة تعيين الموظف بالكامل من الفرع والقسم وحذف الحساب الإداري"""
    try:
        employee = Employee.query.get(emp_id)
        
        if not employee:
            return jsonify({'message': 'الموظف غير موجود'}), 404
        
        print(f"Removing assignment for employee: {employee.full_name}")  # للتشخيص
        
        # حفظ المعلومات القديمة للسجل
        old_branch_name = employee.branch.name if employee.branch else None
        old_department_name = employee.department.name if employee.department else None
        old_user_type = None
        had_admin_account = False
        
        # التحقق من وجود حساب إداري والتعامل معه
        if hasattr(employee, 'user_account') and employee.user_account:
            user_account = employee.user_account
            old_user_type = user_account.user_type
            
            # التحقق مما إذا كان الحساب إداري
            if user_account.user_type in ['branch_head', 'branch_deputy', 'department_head', 'department_deputy']:
                had_admin_account = True
                
                print(f"Found administrative account with type: {old_user_type}")
                
                # التحقق من أن المستخدم الحالي ليس نفس الموظف المراد إزالة منصبه
                if current_user and current_user.employee_id == emp_id:
                    return jsonify({
                        'message': 'لا يمكنك إزالة منصبك الخاص بك'
                    }), 400
                
                # التحقق من الصلاحيات - فقط السوبر أدمن أو رئيس فرع أعلى يمكنه حذف حساب إداري
                if current_user:
                    if not current_user.is_super_admin():
                        # إذا كان المستخدم الحالي رئيس فرع، يمكنه فقط حذف حسابات في نفس الفرع أو أقل
                        if current_user.is_branch_head():
                            if user_account.user_type in ['branch_head'] and current_user.branch_id != user_account.branch_id:
                                return jsonify({
                                    'message': 'ليس لديك صلاحية لإزالة منصب رئيس فرع من فرع آخر'
                                }), 403
                        else:
                            return jsonify({
                                'message': 'ليس لديك صلاحية لإزالة المناصب الإدارية'
                            }), 403
                
                # حذف السجلات المرتبطة قبل حذف الحساب الإداري
                print(f"Deleting related records for user account {user_account.id}")
                
                # حذف المعاملات المرتبطة بهذا المستخدم
                from app.models.transaction import Transaction, TransactionApproval
                
                # حذف الموافقات على المعاملات
                transaction_approvals = TransactionApproval.query.filter_by(approver_id=user_account.id).all()
                for approval in transaction_approvals:
                    db.session.delete(approval)
                print(f"Deleted {len(transaction_approvals)} transaction approvals")
                
                # حذف المعاملات التي طلبها هذا المستخدم
                user_transactions = Transaction.query.filter_by(requested_by=user_account.id).all()
                for transaction in user_transactions:
                    # حذف الموافقات المرتبطة بهذه المعاملة أولاً
                    related_approvals = TransactionApproval.query.filter_by(transaction_id=transaction.id).all()
                    for approval in related_approvals:
                        db.session.delete(approval)
                    # ثم حذف المعاملة
                    db.session.delete(transaction)
                print(f"Deleted {len(user_transactions)} transactions")
                
                # حذف أي سجلات أخرى مرتبطة بالمستخدم (يمكن إضافة المزيد حسب الحاجة)
                # مثال: الإجازات، التقارير، إلخ
                
                # حذف الحساب الإداري نهائياً
                print(f"Deleting administrative user account for employee {emp_id}")
                db.session.delete(user_account)
                
                print(f"Successfully deleted administrative account: {old_user_type}")
            
            elif user_account.user_type == 'employee':
                # إذا كان الحساب موظف عادي، فقط قم بتحديث البيانات
                user_account.branch_id = None
                user_account.department_id = None
                print(f"Updated regular employee account")
        
        # إزالة تعيين الفرع والقسم من الموظف
        employee.branch_id = None
        employee.department_id = None
        
        # تنفيذ التغييرات
        db.session.commit()
        
        print(f"Successfully removed assignment for employee {emp_id}")
        
        # رسالة مخصصة حسب ما تم حذفه
        message = 'تم إزالة تعيين الموظف بنجاح'
        if had_admin_account:
            message += ' وحذف الحساب الإداري'
        
        return jsonify({
            'message': message,
            'employee': {
                'id': employee.id,
                'full_name': employee.full_name,
                'old_branch': old_branch_name,
                'old_department': old_department_name,
                'old_user_type': old_user_type,
                'admin_account_deleted': had_admin_account,
                'branch_id': None,
                'branch_name': None,
                'department_id': None,
                'department_name': None,
                'is_department_head': False,
                'is_branch_head': False
            }
        }), 200
    
    except Exception as e:
        db.session.rollback()
        print(f"Error removing employee assignment: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'message': 'حدث خطأ أثناء إزالة تعيين الموظف',
            'error': str(e)
        }), 500