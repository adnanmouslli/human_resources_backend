from datetime import date
import os
from werkzeug.utils import secure_filename
from app import db
from app.models import Employee, Attendance, Advance, ProductionMonitoring, MonthlyAttendance

from app.models import Employee, Attendance, Advance, ProductionMonitoring, MonthlyAttendance




# تحديد المجلدات المسموح بها لحفظ الملفات
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class EmployeeController:
    @staticmethod
    def create_employee(data, certificate_file=None):
        # Validate required fields
        required_fields = ['fingerprint_id', 'full_name', 'employee_type', 'work_system']
        missing_fields = [field for field in required_fields if field not in data or not data[field]]
        if missing_fields:
            return {'message': f'Missing fields: {", ".join(missing_fields)}'}, 400

        # Additional validation based on employee type
        if data['employee_type'] == 'permanent' and 'position' not in data:
            return {'message': 'Position is required for permanent employees'}, 400
        elif data['employee_type'] == 'temporary' and 'profession' not in data:
            return {'message': 'Profession is required for temporary employees'}, 400

        # معالجة ملف الشهادة إذا تم تقديمه
        certificate_path = None
        if certificate_file and certificate_file.filename != '' and allowed_file(certificate_file.filename):
            filename = secure_filename(certificate_file.filename)
            unique_filename = f"{data['fingerprint_id']}_{filename}"
            certificates_folder = os.path.join(os.getenv('UPLOAD_FOLDER'), 'certificates')
            if not os.path.exists(certificates_folder):
                os.makedirs(certificates_folder)
            file_path = os.path.join(certificates_folder, unique_filename)
            certificate_file.save(file_path)
            certificate_path = f"/uploads/certificates/{unique_filename}"

        try:
            birth_date_value = data.get('birth_date') if data.get('birth_date') and data['birth_date'] != 'null' else None
            joining_date_value = data.get('date_of_joining') if data.get('date_of_joining') and data['date_of_joining'] != 'null' else None
            insurance_start_date_value = data.get('insurance_start_date') if data.get('insurance_start_date') and data['insurance_start_date'] != 'null' else None
            insurance_end_date_value = data.get('insurance_end_date') if data.get('insurance_end_date') and data['insurance_end_date'] != 'null' else None

            employee = Employee(
                fingerprint_id=data['fingerprint_id'],
                full_name=data['full_name'],
                employee_type=data['employee_type'],
                position=data.get('position') if data['employee_type'] == 'permanent' else None,
                profession_id=data.get('profession') if data['employee_type'] == 'temporary' else None,
                salary=data.get('salary', 0),
                advancePercentage=data.get('advancePercentage'),
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
                shift_id=data.get('shift_id'),
                insurance_deduction=data.get('insurance_deduction', 0),
                allowances=data.get('allowances', 0),
                insurance_start_date=insurance_start_date_value,
                insurance_end_date=insurance_end_date_value,
            )
            db.session.add(employee)
            db.session.commit()
            return {
                'message': 'Employee created',
                'employee': {
                    'id': employee.id,
                    'full_name': employee.full_name,
                    'certificates': employee.certificates
                }
            }, 201
        except Exception as e:
            return {'message': 'Error creating employee', 'error': str(e)}, 500

    @staticmethod
    def get_all_employees():
        employees = Employee.query.all()
        return [{
            'id': emp.id,
            'fingerprint_id': emp.fingerprint_id,
            'full_name': emp.full_name,
            'employee_type': emp.employee_type,
            'position': emp.job_title.title_name if emp.job_title else None,
            'profession': emp.profession.name if emp.profession else None,
            'salary': float(emp.salary),
            'allowances': float(emp.allowances) if emp.allowances else 0,
            'insurance_deduction': float(emp.insurance_deduction) if emp.insurance_deduction else 0,
            'advancePercentage': float(emp.advancePercentage) if emp.advancePercentage else 0,
            'work_system': emp.work_system,
            'certificates': emp.certificates,
            'date_of_birth': emp.date_of_birth.isoformat() if emp.date_of_birth else None,
            'place_of_birth': emp.place_of_birth,
            'id_card_number': emp.id_card_number,
            'national_id': emp.national_id,
            'residence': emp.residence,
            'mobile_1': emp.mobile_1,
            'mobile_2': emp.mobile_2,
            'mobile_3': emp.mobile_3,
            'worker_agreement': emp.worker_agreement,
            'notes': emp.notes,
            'shift_id': emp.shift_id,
            'insurance_start_date': emp.insurance_start_date,
            'insurance_end_date': emp.insurance_end_date,
            'created_at': emp.created_at.isoformat(),
            'updated_at': emp.updated_at.isoformat()
        } for emp in employees], 200

    @staticmethod
    def get_employee_by_id(id):
        employee = Employee.query.get(id)
        if not employee:
            return {'message': 'Employee not found'}, 404
        return {
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
            'updated_at': employee.updated_at.isoformat()
        }, 200

    @staticmethod
    def update_employee(id, data):
        employee = Employee.query.get(id)
        if not employee:
            return {'message': 'Employee not found'}, 404
        for key, value in data.items():
            if hasattr(employee, key):
                setattr(employee, key, value)
        db.session.commit()
        return {
            'message': 'Employee updated',
            'employee': {
                'id': employee.id,
                'full_name': employee.full_name,
                'position': employee.position
            }
        }, 200

    @staticmethod
    def delete_employee(id):
        employee = Employee.query.get(id)
        if not employee:
            return {'message': 'Employee not found'}, 404
        has_attendances = Attendance.query.filter_by(empId=id).first()
        has_advances = Advance.query.filter_by(employee_id=id).first()
        has_production = ProductionMonitoring.query.filter_by(employee_id=id).first()
        has_monthly_attendance = MonthlyAttendance.query.filter_by(employee_id=id).first()
        if has_attendances or has_advances or has_production or has_monthly_attendance:
            return {
                'status': 400,
                'message': 'لا يمكن حذف هذا الموظف بسبب وجود سجلات مرتبطة.'
            }, 200
        db.session.delete(employee)
        db.session.commit()
        return {
            'status': 200,
            'message': 'Employee deleted successfully'
        }, 200

    @staticmethod
    def get_absent_employees(selected_date=date.today().isoformat()):
        try:
            absent_employees = db.session.query(Employee).filter(
                ~Employee.id.in_(
                    db.session.query(Attendance.empId).filter(
                        db.func.cast(Attendance.createdAt, db.Date) == selected_date
                    )
                )
            ).all()
            result = [
                {
                    'id': emp.id,
                    'full_name': emp.full_name,
                }
                for emp in absent_employees
            ]
            return result, 200
        except Exception as e:
            return {'message': 'Error fetching absent employees', 'error': str(e)}, 500

    @staticmethod
    def get_employees_by_system(system):
        try:
            employees = Employee.query.filter(
                Employee.work_system == system
            ).order_by(Employee.full_name).all()
            if not employees:
                return [], 200
            return [{
                'id': str(emp.id),
                'full_name': emp.full_name,
            } for emp in employees], 200
        except Exception as e:
            return {
                'message': 'حدث خطأ أثناء جلب بيانات الموظفين',
                'error': str(e)
            }, 500