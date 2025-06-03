from datetime import datetime, time, timedelta
from flask import Blueprint, json, request, jsonify
from sqlalchemy import func ,cast, Date
from app import db
from app.models import Attendance, Employee, Shift
from app.models.user import User
from app.utils import token_required
import json
from json import JSONDecodeError  # استيراد JSONDecodeError مباشرة من مكتبة json


attendance_bp = Blueprint('attendance', __name__)

# Create Attendance
@attendance_bp.route('/api/attendances', methods=['POST'])
@token_required
def create_attendance(user_id):
    data = request.get_json()

    # Validate required fields
    required_fields = ['empId']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return jsonify({'message': f'Missing fields: {", ".join(missing_fields)}'}), 400

    attendance = Attendance(
        empId=data['empId'],
        checkInTime=data['checkInTime'],  # تأكد من أن القيمة في الصيغة الصحيحة
        checkOutTime=data['checkOutTime'],  # تأكد من أن القيمة في الصيغة الصحيحة
    )
    db.session.add(attendance)
    db.session.commit()

    return jsonify({'message': 'Attendance created', 'attendance': {
        'id': attendance.id,
        'empId': attendance.empId,
        'checkInTime': str(attendance.checkInTime),  # Convert to string
        'checkOutTime': str(attendance.checkOutTime) if attendance.checkOutTime else None,  # Convert to string
        'createdAt': str(attendance.createdAt)  # Ensure it's a string
    }}), 201

# ////////////////////////////////////////////////////////////////////////////////////////////////////

# Get All Attendances
@attendance_bp.route('/api/attendances', methods=['GET'])
@token_required
def get_all_attendances(user):
    # الحصول على المستخدم من جدول User
    user = User.query.get(user.id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    # جلب الموظفين المسموح له برؤيتهم
    accessible_employees = user.get_accessible_employees()
    accessible_employee_ids = [emp.id for emp in accessible_employees]

    # جلب السجلات فقط للموظفين المتاحين له
    attendances = Attendance.query.filter(Attendance.empId.in_(accessible_employee_ids)).all()

    # تجهيز البيانات للرد
    result = []
    for att in attendances:
        result.append({
            'id': att.id,
            'empId': att.empId,
            'checkInTime': att.checkInTime.isoformat() if att.checkInTime else None,
            'checkOutTime': att.checkOutTime.isoformat() if att.checkOutTime else None,
            'createdAt': att.createdAt.isoformat() if att.createdAt else None
        })

    return jsonify(result), 200



# Get Attendance by ID
@attendance_bp.route('/api/attendances/<int:id>', methods=['GET'])
@token_required
def get_attendance(user_id, id):
    attendance = Attendance.query.get(id)

    if not attendance:
        return jsonify({'message': 'Attendance not found'}), 404

    return jsonify({
        'id': attendance.id,
        'empId': attendance.empId,
        'checkInTime': str(attendance.checkInTime),  # Convert to string
        'checkOutTime': str(attendance.checkOutTime) if attendance.checkOutTime else None,  # Convert to string
        'createdAt': str(attendance.createdAt)  # Ensure it's a string
    }), 200


# Update Attendance
@attendance_bp.route('/api/attendances/<int:id>', methods=['PUT'])
@token_required
def update_attendance(user_id, id):
    attendance = Attendance.query.get(id)

    if not attendance:
        return jsonify({'message': 'Attendance not found'}), 404

    data = request.get_json()

    for key, value in data.items():
        if hasattr(attendance, key):
            setattr(attendance, key, value)

    db.session.commit()

    return jsonify({'message': 'Attendance updated', 'attendance': {
        'id': attendance.id,
        'empId': attendance.empId,
        'checkInTime': str(attendance.checkInTime),  # Convert to string
        'checkOutTime': str(attendance.checkOutTime) if attendance.checkOutTime else None,  # Convert to string
        'createdAt': str(attendance.createdAt)  # Ensure it's a string
    }}), 200


# Delete Attendance
@attendance_bp.route('/api/attendances/<int:id>', methods=['DELETE'])
@token_required
def delete_attendance(user_id, id):
    attendance = Attendance.query.get(id)

    if not attendance:
        return jsonify({'message': 'Attendance not found'}), 404

    db.session.delete(attendance)
    db.session.commit()

    return jsonify({'message': 'Attendance deleted'}), 200



@attendance_bp.route('/api/attendances/employee/<int:empId>/date/<date_str>', methods=['DELETE'])
@token_required
def delete_employee_daily_attendance(user_id, empId, date_str):
    """
    حذف جميع سجلات الحضور للموظف في تاريخ معين
    """
    try:
        # التحقق من صحة تنسيق التاريخ
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # البحث عن الموظف للتأكد من وجوده
        employee = Employee.query.get(empId)
        if not employee:
            return jsonify({
                'status': 'error',
                'message': f'Employee with ID {empId} not found'
            }), 404
        
        # العثور على جميع سجلات الحضور للموظف في التاريخ المحدد
        attendance_records = Attendance.query.filter(
            Attendance.empId == empId,
            cast(Attendance.createdAt, Date) == target_date
        ).all()
        
        if not attendance_records:
            return jsonify({
                'status': 'warning',
                'message': f'No attendance records found for employee {employee.full_name} on {date_str}'
            }), 404
        
        # حفظ معلومات السجلات المحذوفة للعرض في الرد
        deleted_records_info = []
        for record in attendance_records:
            deleted_records_info.append({
                'id': record.id,
                'checkInTime': str(record.checkInTime) if record.checkInTime else None,
                'checkOutTime': str(record.checkOutTime) if record.checkOutTime else None,
                'checkInReason': record.checkInReason,
                'checkOutReason': record.checkOutReason
            })
        
        # حذف جميع السجلات
        for record in attendance_records:
            db.session.delete(record)
        
        # حفظ التغييرات في قاعدة البيانات
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': f'Successfully deleted {len(attendance_records)} attendance record(s) for {employee.full_name} on {date_str}',
            'data': {
                'employee_id': empId,
                'employee_name': employee.full_name,
                'date': date_str,
                'deleted_records_count': len(attendance_records),
                'deleted_records': deleted_records_info
            }
        }), 200
        
    except ValueError:
        return jsonify({
            'status': 'error',
            'message': 'Invalid date format. Please use YYYY-MM-DD'
        }), 400
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': f'Error deleting attendance records: {str(e)}'
        }), 500


@attendance_bp.route('/api/attendances/employee/<int:empId>/date/<date_str>/period/<int:attendance_id>', methods=['DELETE'])
@token_required  
def delete_single_attendance_period(user_id, empId, date_str, attendance_id):
    """
    حذف فترة حضور واحدة محددة (سجل واحد فقط)
    """
    try:
        # التحقق من صحة تنسيق التاريخ
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # البحث عن السجل المحدد
        attendance_record = Attendance.query.filter(
            Attendance.id == attendance_id,
            Attendance.empId == empId,
            cast(Attendance.createdAt, Date) == target_date
        ).first()
        
        if not attendance_record:
            return jsonify({
                'status': 'error',
                'message': 'Attendance record not found'
            }), 404
        
        # حفظ معلومات السجل المحذوف
        deleted_record_info = {
            'id': attendance_record.id,
            'employee_name': attendance_record.employee.full_name,
            'checkInTime': str(attendance_record.checkInTime) if attendance_record.checkInTime else None,
            'checkOutTime': str(attendance_record.checkOutTime) if attendance_record.checkOutTime else None,
            'checkInReason': attendance_record.checkInReason,
            'checkOutReason': attendance_record.checkOutReason
        }
        
        # حذف السجل
        db.session.delete(attendance_record)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': f'Successfully deleted attendance period for {attendance_record.employee.full_name}',
            'data': deleted_record_info
        }), 200
        
    except ValueError:
        return jsonify({
            'status': 'error',
            'message': 'Invalid date format. Please use YYYY-MM-DD'
        }), 400
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': f'Error deleting attendance record: {str(e)}'
        }), 500
    
# Check-in Attendance for Employee
@attendance_bp.route('/api/attendances/checkin', methods=['POST'])
@token_required
def check_in(user_id):
    data = request.get_json()

    # Validate required fields
    if 'empId' not in data:
        return jsonify({'message': 'Employee ID is required'}), 400

    # Get employee from empId
    employee = Employee.query.get(data['empId'])
    if not employee:
        return jsonify({'message': 'Employee not found'}), 404

    # التحقق من عدم وجود تسجيل حضور مفتوح (بدون تسجيل خروج) لهذا الموظف
    existing_open_attendance = (
        Attendance.query.filter(
            Attendance.empId == data['empId'],
            cast(Attendance.createdAt, Date) == datetime.now().date(),
            Attendance.checkOutTime == None  # فقط السجلات التي لا يوجد لها وقت خروج
        )
        .first()
    )

    if existing_open_attendance:
        return jsonify({'message': 'Employee has an open check-in without check-out'}), 400

    # استخدام وقت حضور مخصص إذا تم تقديمه، وإلا استخدام الوقت الحالي
    if 'checkInTime' in data and data['checkInTime']:
        try:
            # تحويل النص إلى كائن time
            time_parts = data['checkInTime'].split(':')
            hour = int(time_parts[0])
            minute = int(time_parts[1])
            second = int(time_parts[2]) if len(time_parts) > 2 else 0
            
            check_in_time = time(hour, minute, second)
        except (ValueError, IndexError):
            # في حالة وجود خطأ في تنسيق الوقت، استخدم الوقت الحالي
            check_in_time = datetime.now().time()
            print(f"Error parsing checkInTime: {data['checkInTime']}. Using current time instead.")
    else:
        # استخدام الوقت الحالي إذا لم يتم تقديم وقت مخصص
        check_in_time = datetime.now().time()

    # تحديد وقت الخروج الافتراضي (وقت نهاية الوردية)
    default_check_out_time = None
    check_out_reason = None
    
    # البحث عن وردية الموظف إذا كان يعمل بنظام الورديات
    if employee.work_system == 'shift' and employee.shift_id:
        shift = Shift.query.get(employee.shift_id)
        if shift and shift.end_time:
            default_check_out_time = shift.end_time
            check_out_reason = f'Default shift end time - {shift.name}'
        else:
            # إذا لم توجد وردية محددة، استخدم وقت افتراضي
            default_check_out_time = time(19, 0)  # 7:00 PM
            check_out_reason = 'Default end time (19:00) - No shift defined'
    else:
        # للموظفين الذين لا يعملون بنظام الورديات، استخدم وقت افتراضي
        default_check_out_time = time(18, 0)  # 6:00 PM for non-shift workers
        check_out_reason = 'Default end time (18:00) - Hours-based worker'

    # إنشاء تسجيل حضور جديد مع الوقت المخصص ووقت الخروج الافتراضي
    attendance = Attendance(
        empId=data['empId'],
        checkInTime=check_in_time,
        checkOutTime=default_check_out_time,  # إضافة وقت الخروج الافتراضي
        createdAt=datetime.now(),
        checkInReason=data.get('checkInReason', 'Manual check-in'),  # إضافة سبب الدخول
        checkOutReason=check_out_reason  # إضافة سبب الخروج الافتراضي
    )

    db.session.add(attendance)
    db.session.commit()

    # الحصول على بيانات الموظف لإرجاعها في الاستجابة
    employee_data = {
        'id': employee.id,
        'name': employee.full_name,
        'work_system': employee.work_system,
        'shift_id': employee.shift_id
    }

    # إضافة معلومات الوردية إذا كانت موجودة
    shift_data = None
    if employee.shift_id:
        shift = Shift.query.get(employee.shift_id)
        if shift:
            shift_data = {
                'id': shift.id,
                'name': shift.name,
                'start_time': str(shift.start_time),
                'end_time': str(shift.end_time)
            }

    return jsonify({
        'message': 'Check-in successful with default check-out time',
        'attendance': {
            'id': attendance.id,
            'employee': employee_data,
            'shift': shift_data,
            'createdAt': str(attendance.createdAt),
            'checkInTime': str(attendance.checkInTime),
            'checkOutTime': str(attendance.checkOutTime),  # إرجاع وقت الخروج الافتراضي
            'actualCheckIn': str(attendance.checkInTime),
            'defaultCheckOut': str(attendance.checkOutTime),
            'checkInReason': attendance.checkInReason,
            'checkOutReason': attendance.checkOutReason,
            'isDefaultCheckOut': True  # إشارة أن وقت الخروج افتراضي
        }
    }), 201
     
# Get Attendance by Employee ID (empId)
@attendance_bp.route('/api/attendances/employee/<int:empId>', methods=['GET'])
@token_required
def get_attendance_by_empId(user_id, empId):
    # البحث عن حضور الموظف حسب empId
    attendances = Attendance.query.filter_by(empId=empId).all()

    if not attendances:
        return jsonify({'message': 'No attendance records found for this employee'}), 404

    return jsonify([{
        'id': att.id,
        'empId': att.empId,
        'checkInTime': str(att.checkInTime),
        'checkOutTime': str(att.checkOutTime) if att.checkOutTime else None,
        'createdAt': str(att.createdAt)
    } for att in attendances]), 200


# Get Attendance within Date Range (startDate to endDate)
@attendance_bp.route('/api/attendances/range', methods=['GET'])
@token_required
def get_attendance_by_date_range(user_id):
    start_date = request.args.get('startDate')
    end_date = request.args.get('endDate')

    if not start_date or not end_date:
        return jsonify({'message': 'Both startDate and endDate are required'}), 400

    try:
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
        end_date = datetime.strptime(end_date, '%Y-%m-%d')
    except ValueError:
        return jsonify({'message': 'Invalid date format. Please use YYYY-MM-DD'}), 400

    attendances = Attendance.query.filter(Attendance.createdAt >= start_date, Attendance.createdAt <= end_date).all()

    if not attendances:
        return jsonify({'message': 'No attendance records found for the given date range'}), 404

    return jsonify([{
        'id': att.id,
        'empId': att.empId,
        'checkInTime': str(att.checkInTime),
        'checkOutTime': str(att.checkOutTime) if att.checkOutTime else None,
        'createdAt': str(att.createdAt)
    } for att in attendances]), 200
# Set Check-Out Time for Latest Attendance and Update Production Quantity

@attendance_bp.route('/api/attendances/checkout', methods=['POST'])
@token_required
def check_out(user_id):
    data = request.get_json()

    # Validate required fields
    if 'empId' not in data:
        return jsonify({'message': 'Employee ID is required'}), 400

    # Get employee from empId
    employee = Employee.query.get(data['empId'])
    if not employee:
        return jsonify({'message': 'Employee not found'}), 404

    # Get the latest attendance record for today without a check-out time
    latest_attendance = (
        Attendance.query.filter(
            Attendance.empId == data['empId'],
            Attendance.checkOutTime == None,
            cast(Attendance.createdAt, Date) == datetime.now().date()
        )
        .order_by(Attendance.createdAt.desc())
        .first()
    )
    
    if not latest_attendance:
        return jsonify({'message': 'No open attendance records for today found for this employee'}), 404

    # استخدام وقت انصراف مخصص إذا تم تقديمه، وإلا استخدام الوقت الحالي
    if 'checkOutTime' in data and data['checkOutTime']:
        try:
            # تحويل النص إلى كائن time
            time_parts = data['checkOutTime'].split(':')
            hour = int(time_parts[0])
            minute = int(time_parts[1])
            second = int(time_parts[2]) if len(time_parts) > 2 else 0
            
            check_out_time = time(hour, minute, second)
        except (ValueError, IndexError):
            # في حالة وجود خطأ في تنسيق الوقت، استخدم الوقت الحالي
            check_out_time = datetime.now().time()
            print(f"Error parsing checkOutTime: {data['checkOutTime']}. Using current time instead.")
    else:
        # استخدام الوقت الحالي إذا لم يتم تقديم وقت مخصص
        check_out_time = datetime.now().time()

    # Update check-out time and reason
    latest_attendance.checkOutTime = check_out_time
    
    # إضافة سبب الخروج إذا تم تقديمه
    if 'checkOutReason' in data:
        latest_attendance.checkOutReason = data['checkOutReason']
    
    db.session.commit()

    return jsonify({
        'message': 'Check-out time set successfully',
        'attendance': {
            'id': latest_attendance.id,
            'empId': latest_attendance.empId,
            'createdAt': str(latest_attendance.createdAt),
            'checkInTime': str(latest_attendance.checkInTime),
            'checkOutTime': str(latest_attendance.checkOutTime),
            'checkInReason': latest_attendance.checkInReason,
            'checkOutReason': latest_attendance.checkOutReason,

        }
    }), 200



@attendance_bp.route('/api/fingerprint/check-in', methods=['POST'])
def fingerprint_check_in():
    data = request.get_json()
    if not data or 'fingerprint_id' not in data:
        return jsonify({
            'status': 'error',
            'message': 'Fingerprint ID is required'
        }), 400
    
    return jsonify(check_in_by_fingerprint(data['fingerprint_id']))

@attendance_bp.route('/api/fingerprint/check-out', methods=['POST'])
def fingerprint_check_out():
    data = request.get_json()
    if not data or 'fingerprint_id' not in data:
        return jsonify({
            'status': 'error',
            'message': 'Fingerprint ID is required'
        }), 400
    
    return jsonify(check_out_by_fingerprint(data['fingerprint_id']))

@attendance_bp.route('/api/fingerprint/sync', methods=['POST'])
def fingerprint_sync():
    return sync_fingerprint_records()





def check_in_by_fingerprint(fingerprint_id):
    """
    تسجيل دخول الموظف باستخدام رقم بصمته
    """
    # البحث عن الموظف باستخدام رقم البصمة
    employee = Employee.query.filter_by(fingerprint_id=fingerprint_id).first()
    
    if not employee:
        return {
            'status': 'error',
            'message': f'No employee found with fingerprint ID: {fingerprint_id}'
        }, 404
    
    # التحقق من عدم وجود تسجيل حضور مفتوح لهذا الموظف اليوم
    existing_open_attendance = (
        Attendance.query.filter(
            Attendance.empId == employee.id,
            cast(Attendance.createdAt, Date) == datetime.now().date(),
            Attendance.checkOutTime == None
        )
        .first()
    )

    if existing_open_attendance:
        return {
            'status': 'warning',
            'message': f'Employee {employee.full_name} already has an open check-in without check-out'
        }, 400
    
    # إنشاء تسجيل حضور جديد
    attendance = Attendance(
        empId=employee.id,
        checkInTime=datetime.now().time(),
        createdAt=datetime.now(),
        checkInReason='Fingerprint scan'
    )

    db.session.add(attendance)
    db.session.commit()

    return {
        'status': 'success',
        'message': f'Check-in successful for {employee.full_name}',
        'data': {
            'employee_id': employee.id,
            'employee_name': employee.full_name,
            'check_in_time': str(attendance.checkInTime),
            'attendance_id': attendance.id
        }
    }, 201

def check_out_by_fingerprint(fingerprint_id):
    """
    تسجيل خروج الموظف باستخدام رقم بصمته
    """
    # البحث عن الموظف باستخدام رقم البصمة
    employee = Employee.query.filter_by(fingerprint_id=fingerprint_id).first()
    
    if not employee:
        return {
            'status': 'error',
            'message': f'No employee found with fingerprint ID: {fingerprint_id}'
        }, 404
    
    # البحث عن آخر تسجيل حضور مفتوح لهذا الموظف اليوم
    latest_attendance = (
        Attendance.query.filter(
            Attendance.empId == employee.id,
            cast(Attendance.createdAt, Date) == datetime.now().date(),
            Attendance.checkOutTime == None
        )
        .order_by(Attendance.createdAt.desc())
        .first()
    )
    
    if not latest_attendance:
        return {
            'status': 'error',
            'message': f'No open attendance record found for {employee.full_name} today'
        }, 404
    
    # تحديث وقت الخروج
    latest_attendance.checkOutTime = datetime.now().time()
    latest_attendance.checkOutReason = 'Fingerprint scan'
    
    db.session.commit()
    
    return {
        'status': 'success',
        'message': f'Check-out successful for {employee.full_name}',
        'data': {
            'employee_id': employee.id,
            'employee_name': employee.full_name,
            'check_in_time': str(latest_attendance.checkInTime),
            'check_out_time': str(latest_attendance.checkOutTime),
            'attendance_id': latest_attendance.id
        }
    }, 200

# دالة لمزامنة سجلات البصمة مع الحفاظ على السجلات الموجودة وتحديث الخروج فقط
def sync_fingerprint_records():
    """
    مزامنة سجلات البصمة مع النظام الجديد - حماية دقيقة لأوقات الخروج:
    - يُحدث وقت الخروج فقط إذا كان مطابق بالضبط لوقت نهاية الوردية
    - يحمي جميع أوقات الخروج الحقيقية (غير أوقات نهاية الوردية)
    """
    
    def safe_format_time(time_obj, default_text="غير محدد"):
        """تنسيق الوقت بأمان مع التعامل مع القيم None"""
        if time_obj is None:
            return default_text
        
        try:
            if hasattr(time_obj, 'strftime'):
                return time_obj.strftime("%H:%M:%S")
            else:
                return str(time_obj)
        except (AttributeError, TypeError, ValueError) as e:
            print(f"تحذير: مشكلة في تنسيق الوقت {time_obj}: {str(e)}")
            return default_text
    
    def is_shift_end_time_exactly(checkout_time, shift_end_time, tolerance_minutes=2):
        """
        فحص دقيق: هل وقت الخروج المسجل = وقت نهاية الوردية بالضبط؟
        
        المعاملات:
            checkout_time: وقت الخروج المسجل
            shift_end_time: وقت نهاية الوردية المحدد للموظف
            tolerance_minutes: هامش التسامح (2 دقيقة فقط)
        
        العوائد:
            bool: True فقط إذا كان الوقت مطابق لنهاية الوردية
        """
        if checkout_time is None:
            return True  # لا توجد بصمة خروج - يمكن التحديث
        
        # تحديد وقت نهاية الوردية (إما من جدول الوردية أو الافتراضي 19:00)
        if shift_end_time is None:
            default_time = time(19, 0)  # الوقت الافتراضي
            target_time = default_time
        else:
            target_time = shift_end_time
        
        # تحويل الأوقات إلى دقائق للمقارنة الدقيقة
        checkout_minutes = checkout_time.hour * 60 + checkout_time.minute
        target_minutes = target_time.hour * 60 + target_time.minute
        
        # السماح بفرق دقيقتين فقط (للتسامح مع اختلافات التسجيل البسيطة)
        return abs(checkout_minutes - target_minutes) <= tolerance_minutes
    
    try:
        data = request.get_json()
        
        print("البيانات المستلمة:", data)
        
        if not data or 'records' not in data:
            return jsonify({
                'status': 'error',
                'message': 'No records provided for synchronization'
            }), 400
        
        records = data['records']
        
        if not isinstance(records, list) or len(records) == 0:
            return jsonify({
                'status': 'error',
                'message': 'Records must be provided as a non-empty list'
            }), 400
        
        results = {
            'success': 0,
            'failed': 0,
            'updated': 0,
            'created': 0,
            'employees_processed': 0,
            'days_processed': 0,
            'protected_checkouts': 0,  # عدد أوقات الخروج المحمية
            'details': [],
            'processing_summary': []
        }
        
        # تجميع السجلات حسب الموظف والتاريخ
        employee_date_records = {}
        
        print(f"بدء معالجة {len(records)} سجل")
        
        # المرحلة 1: معالجة السجلات الخام وتجميعها حسب الموظف والتاريخ
        for i, record in enumerate(records):
            try:
                print(f"معالجة السجل {i+1}: {record}")
                
                # التحقق من وجود الحقول المطلوبة
                if not all(k in record for k in ('fingerprint_id', 'timestamp')):
                    results['failed'] += 1
                    results['details'].append({
                        'record_index': i,
                        'record': record,
                        'status': 'failed',
                        'reason': 'Missing required fields (fingerprint_id, timestamp)'
                    })
                    continue
                
                fingerprint_id = str(record['fingerprint_id']).strip()
                
                # البحث عن الموظف باستخدام رقم البصمة
                employee = Employee.query.filter_by(fingerprint_id=fingerprint_id).first()
                
                if not employee:
                    results['failed'] += 1
                    results['details'].append({
                        'record_index': i,
                        'fingerprint_id': fingerprint_id,
                        'status': 'failed',
                        'reason': f'No employee found with fingerprint ID: {fingerprint_id}'
                    })
                    continue
                
                # تحويل الطابع الزمني إلى كائن datetime
                try:
                    if isinstance(record['timestamp'], str):
                        record_time = datetime.strptime(record['timestamp'], "%Y-%m-%d %H:%M:%S")
                    else:
                        record_time = record['timestamp']
                    
                    record_date = record_time.date()
                    date_key = record_date.isoformat()
                except (ValueError, TypeError) as e:
                    results['failed'] += 1
                    results['details'].append({
                        'record_index': i,
                        'fingerprint_id': fingerprint_id,
                        'status': 'failed',
                        'reason': f'Invalid timestamp format: {record["timestamp"]} - {str(e)}'
                    })
                    continue
                
                # تجميع البصمات حسب الموظف والتاريخ
                if employee.id not in employee_date_records:
                    employee_date_records[employee.id] = {}
                
                if date_key not in employee_date_records[employee.id]:
                    employee_date_records[employee.id][date_key] = {
                        'employee': employee,
                        'date': record_date,
                        'fingerprint_id': fingerprint_id,
                        'timestamps': []
                    }
                
                # إضافة الطابع الزمني إلى قائمة الأوقات للموظف في هذا اليوم
                employee_date_records[employee.id][date_key]['timestamps'].append({
                    'time': record_time,
                    'status': record.get('status', 0),
                    'punch': record.get('punch', 0),
                    'device_name': record.get('device_name', 'Unknown'),
                    'original_index': i
                })
                
            except Exception as e:
                results['failed'] += 1
                results['details'].append({
                    'record_index': i,
                    'status': 'error',
                    'reason': f'Processing error: {str(e)}'
                })
                print(f"خطأ في معالجة السجل {i}: {str(e)}")
        
        print(f"تم تجميع السجلات لـ {len(employee_date_records)} موظف")
        
        # المرحلة 2: معالجة البصمات لكل موظف ولكل يوم
        for emp_id, date_records in employee_date_records.items():
            employee_name = None
            
            for date_key, day_data in date_records.items():
                try:
                    employee = day_data['employee']
                    employee_name = employee.full_name
                    record_date = day_data['date']
                    timestamps = day_data['timestamps']
                    fingerprint_id = day_data['fingerprint_id']
                    
                    if len(timestamps) == 0:
                        continue
                    
                    # ترتيب البصمات زمنياً
                    timestamps.sort(key=lambda x: x['time'])
                    
                    print(f"معالجة الموظف {employee_name} ({fingerprint_id}) - التاريخ {date_key}: {len(timestamps)} بصمة")
                    
                    # البحث عن سجل حضور موجود لهذا الموظف في هذا اليوم
                    existing_record = Attendance.query.filter(
                        Attendance.empId == emp_id,
                        cast(Attendance.createdAt, Date) == record_date
                    ).first()
                    
                    # استخراج أول وآخر بصمة
                    first_timestamp = timestamps[0]
                    last_timestamp = timestamps[-1] if len(timestamps) > 1 else None
                    
                    if existing_record:
                        # السجل موجود - فحص إمكانية تحديث بصمة الخروج
                        print(f"تم العثور على سجل موجود للموظف {employee_name} في {date_key}")
                        
                        # الحصول على وقت نهاية الوردية للموظف
                        shift_end_time = None
                        if employee.shift_id:
                            shift = Shift.query.get(employee.shift_id)
                            if shift and shift.end_time:
                                shift_end_time = shift.end_time
                        
                        # إذا لم توجد وردية محددة، استخدام الوقت الافتراضي
                        default_checkout_time = shift_end_time if shift_end_time else time(19, 0)
                        
                        # الفحص الدقيق: هل بصمة الخروج الحالية = وقت نهاية الوردية بالضبط؟
                        existing_checkout = existing_record.checkOutTime
                        can_update_checkout = is_shift_end_time_exactly(existing_checkout, shift_end_time)
                        
                        if existing_checkout is None:
                            print(f"لا توجد بصمة خروج للموظف {employee_name} - يمكن التحديث")
                        elif can_update_checkout:
                            shift_time_str = default_checkout_time.strftime('%H:%M:%S')
                            current_time_str = existing_checkout.strftime('%H:%M:%S')
                            print(f"✓ بصمة الخروج للموظف {employee_name} ({current_time_str}) = نهاية الوردية ({shift_time_str}) - يمكن التحديث")
                        else:
                            current_time_str = existing_checkout.strftime('%H:%M:%S')
                            shift_time_str = default_checkout_time.strftime('%H:%M:%S')
                            print(f"🔒 بصمة الخروج للموظف {employee_name} ({current_time_str}) ≠ نهاية الوردية ({shift_time_str}) - محمية من التحديث")
                            results['protected_checkouts'] += 1
                        
                        # تحديث بصمة الخروج حسب الشروط
                        if can_update_checkout:
                            if len(timestamps) > 1:
                                # عدة بصمات - استخدام آخر بصمة إذا كان الفرق منطقي
                                time_diff = (last_timestamp['time'] - first_timestamp['time']).total_seconds()
                                if time_diff > 300:  # أكثر من 5 دقائق
                                    existing_record.checkOutTime = last_timestamp['time'].time()
                                    existing_record.checkOutReason = f'Fingerprint sync update - last of {len(timestamps)} records'
                                    print(f"تم تحديث بصمة الخروج للموظف {employee_name}: {last_timestamp['time'].time().strftime('%H:%M:%S')}")
                                else:
                                    print(f"تم تجاهل تحديث بصمة الخروج للموظف {employee_name} - فرق زمني قصير: {time_diff} ثانية")
                            else:
                                # بصمة واحدة فقط - استخدامها كخروج
                                single_timestamp = first_timestamp['time'].time()
                                existing_check_in_time = existing_record.checkInTime
                                
                                if existing_check_in_time:
                                    existing_minutes = existing_check_in_time.hour * 60 + existing_check_in_time.minute
                                    new_minutes = single_timestamp.hour * 60 + single_timestamp.minute
                                    time_difference_minutes = abs(new_minutes - existing_minutes)
                                    
                                    if time_difference_minutes > 5:
                                        existing_record.checkOutTime = single_timestamp
                                        existing_record.checkOutReason = f'Fingerprint sync - single checkout record'
                                        print(f"تم تحديث بصمة الخروج للموظف {employee_name} (بصمة واحدة): {single_timestamp.strftime('%H:%M:%S')}")
                                    else:
                                        print(f"تم تجاهل البصمة للموظف {employee_name} - قريبة من وقت الدخول ({time_difference_minutes} دقيقة)")
                                else:
                                    existing_record.checkOutTime = single_timestamp
                                    existing_record.checkOutReason = f'Fingerprint sync - checkout for existing record'
                                    print(f"تم تحديث بصمة الخروج للموظف {employee_name} (لا يوجد دخول مسجل): {single_timestamp.strftime('%H:%M:%S')}")
                        
                        results['updated'] += 1
                        
                        # تسجيل معلومات المعالجة
                        existing_check_in = safe_format_time(existing_record.checkInTime)
                        updated_check_out = safe_format_time(existing_record.checkOutTime)
                        
                        processing_info = {
                            'employee_id': employee.id,
                            'employee_name': employee.full_name,
                            'fingerprint_id': fingerprint_id,
                            'date': date_key,
                            'status': 'updated',
                            'action': 'checkout_time_updated' if can_update_checkout else 'checkout_protected',
                            'total_fingerprints': len(timestamps),
                            'existing_check_in': existing_check_in,
                            'updated_check_out': updated_check_out,
                            'checkout_was_protected': not can_update_checkout,
                            'shift_end_time': safe_format_time(default_checkout_time),
                            'all_timestamps': [ts['time'].strftime("%H:%M:%S") for ts in timestamps]
                        }
                        
                        results['processing_summary'].append(processing_info)
                        status_msg = "🔒 محمي" if not can_update_checkout else "✓ محدث"
                        print(f"تم معالجة سجل الموظف {employee_name}: دخول {existing_check_in}, خروج {status_msg} {updated_check_out}")
                        
                    else:
                        # لا يوجد سجل - إنشاء سجل جديد
                        print(f"لا يوجد سجل للموظف {employee_name} في {date_key} - إنشاء سجل جديد")
                        
                        check_in_time = first_timestamp['time'].time()
                        check_out_time = None
                        check_out_reason = None
                        
                        if len(timestamps) == 1:
                            # بصمة واحدة فقط - استخدام وقت نهاية الوردية كخروج افتراضي
                            shift_end_time = None
                            shift = None
                            if employee.shift_id:
                                shift = Shift.query.get(employee.shift_id)
                                if shift and shift.end_time:
                                    shift_end_time = shift.end_time
                            
                            check_out_time = shift_end_time if shift_end_time else time(19, 0)
                            check_out_reason = f'Shift end time - single fingerprint (Shift: {shift.name if shift else "Default"})'
                            print(f"بصمة واحدة للموظف {employee_name} - وضع خروج: {check_out_time}")
                        else:
                            # عدة بصمات - استخدام آخر بصمة كخروج
                            time_diff = (last_timestamp['time'] - first_timestamp['time']).total_seconds()
                            if time_diff > 300:
                                check_out_time = last_timestamp['time'].time()
                                check_out_reason = f'Fingerprint sync - last of {len(timestamps)} records'
                                print(f"عدة بصمات للموظف {employee_name} - استخدام آخر بصمة: {check_out_time.strftime('%H:%M:%S')}")
                            else:
                                # فرق زمني قصير - استخدام نهاية الوردية
                                shift_end_time = None
                                shift = None
                                if employee.shift_id:
                                    shift = Shift.query.get(employee.shift_id)
                                    if shift and shift.end_time:
                                        shift_end_time = shift.end_time
                                
                                check_out_time = shift_end_time if shift_end_time else time(19, 0)
                                check_out_reason = f'Shift end time - short time difference (Shift: {shift.name if shift else "Default"})'
                                print(f"فرق زمني قصير للموظف {employee_name} - وضع خروج من الوردية: {check_out_time}")
                        
                        # إنشاء سجل حضور جديد
                        attendance = Attendance(
                            empId=employee.id,
                            checkInTime=check_in_time,
                            createdAt=first_timestamp['time'],
                            checkInReason=f'Fingerprint sync - first of {len(timestamps)} records',
                            checkOutTime=check_out_time,
                            checkOutReason=check_out_reason
                        )
                        
                        db.session.add(attendance)
                        results['created'] += 1
                        
                        check_in_formatted = safe_format_time(check_in_time)
                        check_out_formatted = safe_format_time(check_out_time)
                        
                        processing_info = {
                            'employee_id': employee.id,
                            'employee_name': employee.full_name,
                            'fingerprint_id': fingerprint_id,
                            'date': date_key,
                            'status': 'created',
                            'action': 'new_record_created',
                            'total_fingerprints': len(timestamps),
                            'check_in_time': check_in_formatted,
                            'check_out_time': check_out_formatted,
                            'check_out_type': 'fingerprint' if len(timestamps) > 1 and time_diff > 300 else 'shift_end',
                            'all_timestamps': [ts['time'].strftime("%H:%M:%S") for ts in timestamps]
                        }
                        
                        results['processing_summary'].append(processing_info)
                        print(f"✓ تم إنشاء سجل جديد للموظف {employee_name}: دخول {check_in_formatted}, خروج {check_out_formatted}")
                    
                    results['success'] += 1
                    
                except Exception as e:
                    error_msg = f"خطأ في معالجة الموظف {employee_name or emp_id} في التاريخ {date_key}: {str(e)}"
                    print(error_msg)
                    results['failed'] += 1
                    results['details'].append({
                        'employee_id': emp_id,
                        'date': date_key,
                        'status': 'error',
                        'reason': error_msg
                    })
        
        # إحصائيات العملية
        results['employees_processed'] = len(employee_date_records)
        results['days_processed'] = sum(len(date_records) for date_records in employee_date_records.values())
        
        # حفظ التغييرات في قاعدة البيانات
        try:
            db.session.commit()
            print(f"تم حفظ جميع التغييرات في قاعدة البيانات")
        except Exception as e:
            db.session.rollback()
            print(f"خطأ في حفظ قاعدة البيانات: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f'Database commit failed: {str(e)}',
                'partial_results': results
            }), 500
        
        # إعداد رسالة النجاح مع تفاصيل الحماية
        success_message = f'تمت مزامنة سجلات الحضور بنجاح: '
        success_message += f'{results["success"]} سجل تم معالجته، '
        success_message += f'{results["created"]} سجل جديد، '
        success_message += f'{results["updated"]} سجل محدث، '
        success_message += f'{results["protected_checkouts"]} وقت خروج محمي، '
        success_message += f'{results["failed"]} فشل، '
        success_message += f'{results["employees_processed"]} موظف، '
        success_message += f'{results["days_processed"]} يوم'
        
        print("انتهاء المعالجة بنجاح")
        print(f"الملخص: {success_message}")
        print(f"أوقات الخروج المحمية: {results['protected_checkouts']}")
        
        return jsonify({
            'status': 'success',
            'message': success_message,
            'results': results
        }), 200
        
    except Exception as e:
        error_msg = f"خطأ عام في معالجة طلب المزامنة: {str(e)}"
        print(error_msg)
        return jsonify({
            'status': 'error',
            'message': error_msg
        }), 500
    
    
@attendance_bp.route('/api/attendances/summary', methods=['GET'])
@token_required
def get_all_attendance_summary(user_id):
    date_str = request.args.get('startDate')
    branch_id = request.args.get('branch_id', type=int)
    department_id = request.args.get('department_id', type=int)
    shift_id = request.args.get('shift_id', type=int)
    filter_incomplete = request.args.get('incomplete', type=int)  # 1 أو 0

    if not date_str:
        return jsonify({'message': 'Date parameter is required'}), 400

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d')
        start_datetime = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_datetime = start_datetime + timedelta(days=1)

        # الحصول على سجلات الحضور لليوم المحدد
        attendances = Attendance.query.filter(
            Attendance.createdAt >= start_datetime,
            Attendance.createdAt < end_datetime
        ).all()

        if not attendances:
            return jsonify({'message': 'No attendance records found for the given date'}), 200

        result = []

        for emp_id in set(att.empId for att in attendances):
            employee_attendances = [att for att in attendances if att.empId == emp_id]
            employee = employee_attendances[0].employee

            # تطبيق الفلاتر حسب الفرع، القسم، الوردية
            if branch_id and employee.branch_id != branch_id:
                continue
            if department_id and employee.department_id != department_id:
                continue
            if shift_id and getattr(employee, 'shift_id', None) != shift_id:
                continue

            # فلتر السجلات الناقصة (بصمات غير مكتملة)
            if filter_incomplete:
                total_checkins = sum(1 for a in employee_attendances if a.checkInTime is not None)
                total_checkouts = sum(1 for a in employee_attendances if a.checkOutTime is not None)

                if total_checkins == 0 or total_checkouts == 0 or total_checkins != total_checkouts:
                    pass  # سجلات ناقصة - نسمح بالإدراج
                else:
                    continue  # السجلات مكتملة - لا ندرجها

            # اختيار نظام الحضور حسب work_system
            if employee.work_system == 'shift':
                attendance_summary = process_shift_attendance(employee, employee_attendances, date_str)
            else:
                attendance_summary = process_hours_attendance(employee, employee_attendances, date_str)

            if attendance_summary:
                result.append(attendance_summary)

        return jsonify(result), 200

    except ValueError:
        return jsonify({'message': 'Invalid date format. Please use YYYY-MM-DD'}), 400
    except Exception as e:
        print(f"Error processing attendance summary: {str(e)}")
        return jsonify({'message': 'Error processing attendance records', 'error': str(e)}), 500


@attendance_bp.route('/api/attendances/filter-by-status', methods=['GET'])
@token_required
def filter_employees_by_status(user_id):
    date_str = request.args.get('date')
    status_filter = request.args.get('status')  # 'حاضر' or 'متاخر' or 'غائب'

    if not date_str:
        return jsonify({'message': 'التاريخ مطلوب'}), 400

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'message': 'تنسيق التاريخ غير صحيح، يجب أن يكون YYYY-MM-DD'}), 400

    employees = Employee.query.all()
    results = []

    for employee in employees:
        attendance = Attendance.query.filter(
            Attendance.empId == employee.id,
            cast(Attendance.createdAt, Date) == target_date
        ).first()

        check_in_time = None
        emp_status = 'غائب'

        if attendance and attendance.checkInTime:
            check_in_time = str(attendance.checkInTime)

            if employee.work_system == 'shift':
                shift = Shift.query.get(employee.shift_id)
                if shift:
                    shift_start_seconds = time_to_seconds(shift.start_time)
                    checkin_seconds = time_to_seconds(attendance.checkInTime)
                    delay_allowed_seconds = shift.allowed_delay_minutes * 60

                    if checkin_seconds > shift_start_seconds + delay_allowed_seconds:
                        emp_status = 'متاخر'
                    else:
                        emp_status = 'حاضر'
                else:
                    emp_status = 'غير محدد (لا يوجد وردية)'
            else:
                # لأي نظام غير الوردية: يعتبر حاضر إذا عنده تسجيل دخول
                emp_status = 'حاضر'
        else:
            # لا يوجد تسجيل دخول ➜ غائب
            emp_status = 'غائب'

        # تطبيق الفلتر
        if status_filter is None or emp_status == status_filter:
            results.append({
                'employee_id': employee.id,
                'full_name': employee.full_name,
                'work_system': employee.work_system,
                'check_in_time': check_in_time,
                'status': emp_status
            })

    return jsonify(results), 200


def process_shift_attendance(employee, employee_attendances, date_str):
    """معالجة حضور الموظف في نظام الورديات"""
    shift = Shift.query.filter_by(id=employee.shift_id).first()
    if not shift:
        return None

    # الأوقات الفعلية من قاعدة البيانات
    first_check_in = min(att.checkInTime for att in employee_attendances if att.checkInTime)
    last_check_out = max(
        (att.checkOutTime for att in employee_attendances if att.checkOutTime),
        default=None
    )

    # حساب أوقات الحضور والانصراف المُطبقة حسب نظام الورديات
    allowed_delay = timedelta(minutes=shift.allowed_delay_minutes)
    allowed_exit = timedelta(minutes=shift.allowed_exit_minutes)

    shift_start_time = time_to_seconds(shift.start_time)
    shift_end_time = time_to_seconds(shift.end_time)
    first_check_in_seconds = time_to_seconds(first_check_in)
    last_check_out_seconds = time_to_seconds(last_check_out) if last_check_out else None

    # حساب حالة الحضور والوقت المُطبق
    if first_check_in_seconds <= shift_start_time + allowed_delay.total_seconds():
        # الموظف في الوقت المحدد - نطبق وقت بداية الوردية
        calculated_check_in_time = shift.start_time
        check_in_status = "On Time"
    else:
        # الموظف متأخر - نطبق الوقت الفعلي
        calculated_check_in_time = first_check_in
        check_in_status = "Late"

    # حساب حالة الانصراف والوقت المُطبق
    if last_check_out:
        if last_check_out_seconds >= shift_end_time - allowed_exit.total_seconds():
            # الموظف انصرف في الوقت المحدد أو بعده - نطبق وقت نهاية الوردية
            calculated_check_out_time = shift.end_time
            check_out_status = "On Time"
        else:
            # الموظف انصرف مبكراً - نطبق الوقت الفعلي
            calculated_check_out_time = last_check_out
            check_out_status = "Early"
    else:
        calculated_check_out_time = None
        check_out_status = "No Check-out"

    # حساب إجمالي وقت العمل والاستراحة
    total_work_time, total_break_time = calculate_work_and_break_time(employee_attendances)

    # إرسال كل من الأوقات المحسوبة والفعلية
    return format_attendance_summary(
        employee, date_str, 
        calculated_check_in_time,  # الوقت المحسوب حسب نظام الورديات
        check_in_status,
        calculated_check_out_time,  # الوقت المحسوب حسب نظام الورديات
        check_out_status, 
        total_work_time,
        total_break_time, 
        employee_attendances  # البيانات الفعلية من قاعدة البيانات
    )

def process_hours_attendance(employee, employee_attendances, date_str):
    """معالجة حضور الموظف في نظام الساعات"""
    # في نظام الساعات، نستخدم الأوقات الفعلية كما هي
    first_check_in = min(att.checkInTime for att in employee_attendances if att.checkInTime)
    last_check_out = max(
        (att.checkOutTime for att in employee_attendances if att.checkOutTime),
        default=None
    )

    # في نظام الساعات، نعتبر كل تسجيل دخول وخروج كفترة عمل منفصلة
    total_work_time, total_break_time = calculate_work_and_break_time(employee_attendances)

    # لا نحتاج لحساب التأخير في نظام الساعات - الأوقات الفعلية هي المُطبقة
    check_in_status = "Recorded"
    check_out_status = "Recorded" if last_check_out else "No Check-out"

    return format_attendance_summary(
        employee, date_str, 
        first_check_in,  # نفس الوقت الفعلي
        check_in_status,
        last_check_out,  # نفس الوقت الفعلي
        check_out_status, 
        total_work_time,
        total_break_time, 
        employee_attendances
    )

def calculate_work_and_break_time(employee_attendances):
    """حساب إجمالي وقت العمل والاستراحة"""
    total_work_time = timedelta()
    total_break_time = timedelta()

    # حساب وقت العمل
    for attendance in employee_attendances:
        if attendance.checkInTime and attendance.checkOutTime:
            work_time_seconds = time_to_seconds(attendance.checkOutTime) - time_to_seconds(attendance.checkInTime)
            total_work_time += timedelta(seconds=work_time_seconds)

    # حساب وقت الاستراحة بين الفترات
    for i in range(1, len(employee_attendances)):
        if employee_attendances[i].checkInTime and employee_attendances[i - 1].checkOutTime:
            break_time_seconds = (
                time_to_seconds(employee_attendances[i].checkInTime) -
                time_to_seconds(employee_attendances[i - 1].checkOutTime)
            )
            total_break_time += timedelta(seconds=break_time_seconds)

    return total_work_time, total_break_time

def format_attendance_summary(employee, date_str, check_in_time, check_in_status,
                            check_out_time, check_out_status, total_work_time,
                            total_break_time, employee_attendances):
    """تنسيق ملخص الحضور مع كامل بيانات الموظف"""
    
    # تحويل أوقات العمل والاستراحة
    total_work_hours, remainder_work = divmod(total_work_time.seconds, 3600)
    total_work_minutes = remainder_work // 60

    total_break_hours, remainder_break = divmod(total_break_time.seconds, 3600)
    total_break_minutes = remainder_break // 60

    # تحديد الإجراء التالي
    last_attendance = max(employee_attendances, key=lambda att: att.id)
    next_action = "check-out" if last_attendance.checkInTime and not last_attendance.checkOutTime else "check-in"

    # تجميع فترات الحضور
    attendance_periods = [{
        'checkInTime': str(att.checkInTime),
        'checkOutTime': str(att.checkOutTime) if att.checkOutTime else None ,
        'checkInReason': att.checkInReason,  # إضافة سبب تسجيل الدخول
        'checkOutReason': att.checkOutReason,  # إضافة سبب تسجيل الخروج
        'attendanceId': att.id  # إضافة معرف سجل الحضور للمرجعية
    } for att in employee_attendances]

    # الحصول على أول وآخر وقت فعلي من قاعدة البيانات
    actual_first_check_in = min(att.checkInTime for att in employee_attendances if att.checkInTime)
    actual_last_check_out = max(
        (att.checkOutTime for att in employee_attendances if att.checkOutTime),
        default=None
    )

    # تجميع بيانات الموظف الكاملة
    employee_data = {
        'id': employee.id,
        'fingerprint_id': employee.fingerprint_id,
        'full_name': employee.full_name,
        'employee_type': employee.employee_type,
        'position': employee.position,
        'profession_id': employee.profession_id,
        'salary': float(employee.salary) if employee.salary else 0,
        'advancePercentage': float(employee.advancePercentage) if employee.advancePercentage else None,
        'certificates': employee.certificates,
        'date_of_birth': employee.date_of_birth.isoformat() if employee.date_of_birth else None,
        'place_of_birth': employee.place_of_birth,
        'id_card_number': employee.id_card_number,
        'national_id': employee.national_id,
        'residence': employee.residence,
        'mobile_1': employee.mobile_1,
        'mobile_2': employee.mobile_2,
        'mobile_3': employee.mobile_3,
        'work_system': employee.work_system,
        'shift_id': employee.shift_id,
        'worker_agreement': employee.worker_agreement,
        'notes': employee.notes,
        'insurance_deduction': float(employee.insurance_deduction) if employee.insurance_deduction else 0,
        'allowances': float(employee.allowances) if employee.allowances else 0,
        'date_of_joining': employee.date_of_joining.isoformat() if employee.date_of_joining else None,
        'created_at': employee.created_at.isoformat() if employee.created_at else None,
        'updated_at': employee.updated_at.isoformat() if employee.updated_at else None
    }

    # إضافة بيانات الوردية إذا كان موظف ورديات
    if employee.shift_id:
        try:
            shift = Shift.query.get(employee.shift_id)
            if shift:
                employee_data['shift'] = {
                    'id': shift.id,
                    'name': shift.name,
                    'start_time': str(shift.start_time),
                    'end_time': str(shift.end_time),
                    'allowed_delay_minutes': shift.allowed_delay_minutes,
                    'allowed_exit_minutes': shift.allowed_exit_minutes
                }
        except Exception as e:
            print(f"Error loading shift data: {str(e)}")

    # إضافة بيانات المسمى الوظيفي إذا كان موظفاً دائماً
    if hasattr(employee, 'job_title') and employee.job_title:
        employee_data['job_title'] = {
            'id': employee.job_title.id,
            'title_name': employee.job_title.title_name
        }

    # إضافة بيانات المهنة إذا كان موظفاً مؤقتاً
    if hasattr(employee, 'profession') and employee.profession:
        employee_data['profession'] = {
            'id': employee.profession.id,
            'name': employee.profession.name,
            'hourly_rate': float(employee.profession.hourly_rate),
            'daily_rate': float(employee.profession.daily_rate)
        }

    # تجميع النتيجة النهائية مع الأوقات الفعلية والمحسوبة
    return {
        'employee': employee_data,
        'date': date_str,
        # الأوقات المحسوبة حسب نظام العمل (للعرض والتقارير)
        'actualCheckIn': str(check_in_time) if check_in_time else None,
        'actualCheckOut': str(check_out_time) if check_out_time else None,
        'checkInStatus': check_in_status,
        'checkOutStatus': check_out_status,
        # الأوقات الفعلية من قاعدة البيانات (للتعديل والمراجعة)
        'firstCheckIn': str(actual_first_check_in) if actual_first_check_in else None,
        'lastCheckOut': str(actual_last_check_out) if actual_last_check_out else None,
        # إحصائيات العمل
        'totalWorkTime': f"{total_work_hours} hours {total_work_minutes} minutes",
        'totalBreakTime': f"{total_break_hours} hours {total_break_minutes} minutes",
        'nextAction': next_action,
        'attendancePeriods': attendance_periods,
        # إضافة معلومات إضافية للتوضيح
        'summary': {
            'total_periods': len(attendance_periods),
            'has_incomplete_checkout': any(period['checkOutTime'] is None for period in attendance_periods),
            'work_system_applied': employee.work_system
        }
    }


def time_to_seconds(t):
    """Convert a time object to seconds since midnight."""
    return t.hour * 3600 + t.minute * 60 + t.second



# إضافة هذه الـ endpoints إلى attendance.py

@attendance_bp.route('/api/attendances/<int:attendance_id>', methods=['PUT'])
@token_required
def update_single_attendance_period(user_id, attendance_id):
    """
    تحديث فترة حضور واحدة
    """
    try:
        # البحث عن سجل الحضور
        attendance = Attendance.query.get(attendance_id)
        if not attendance:
            return jsonify({
                'status': 'error',
                'message': 'Attendance record not found'
            }), 404
        
        data = request.get_json()
        
        # تحديث الحقول المسموح بتعديلها
        updatable_fields = ['checkInTime', 'checkOutTime', 'checkInReason', 'checkOutReason']
        
        for field in updatable_fields:
            if field in data:
                if field in ['checkInTime', 'checkOutTime'] and data[field]:
                    # تحويل النص إلى كائن time
                    try:
                        time_parts = data[field].split(':')
                        hour = int(time_parts[0])
                        minute = int(time_parts[1])
                        second = int(time_parts[2]) if len(time_parts) > 2 else 0
                        setattr(attendance, field, time(hour, minute, second))
                    except (ValueError, IndexError) as e:
                        return jsonify({
                            'status': 'error',
                            'message': f'Invalid time format for {field}: {data[field]}'
                        }), 400
                else:
                    setattr(attendance, field, data[field])
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Attendance period updated successfully',
            'data': {
                'id': attendance.id,
                'empId': attendance.empId,
                'checkInTime': str(attendance.checkInTime) if attendance.checkInTime else None,
                'checkOutTime': str(attendance.checkOutTime) if attendance.checkOutTime else None,
                'checkInReason': attendance.checkInReason,
                'checkOutReason': attendance.checkOutReason
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': f'Error updating attendance: {str(e)}'
        }), 500


@attendance_bp.route('/api/attendances/employee/<int:empId>/date/<date_str>/bulk-update', methods=['PUT'])
@token_required
def bulk_update_employee_attendance(user_id, empId, date_str):
    """
    تحديث جماعي لفترات حضور موظف في تاريخ معين
    """
    try:
        # التحقق من صحة التاريخ
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # التحقق من وجود الموظف
        employee = Employee.query.get(empId)
        if not employee:
            return jsonify({
                'status': 'error',
                'message': f'Employee with ID {empId} not found'
            }), 404
        
        data = request.get_json()
        periods = data.get('periods', [])
        
        if not periods:
            return jsonify({
                'status': 'error',
                'message': 'No periods provided for update'
            }), 400
        
        # حذف جميع السجلات الموجودة لهذا الموظف في هذا التاريخ
        existing_records = Attendance.query.filter(
            Attendance.empId == empId,
            cast(Attendance.createdAt, Date) == target_date
        ).all()
        
        for record in existing_records:
            db.session.delete(record)
        
        # إنشاء السجلات الجديدة
        created_records = []
        for i, period in enumerate(periods):
            try:
                # تحويل أوقات النص إلى كائنات time
                check_in_time = None
                check_out_time = None
                
                if period.get('checkInTime'):
                    time_parts = period['checkInTime'].split(':')
                    hour = int(time_parts[0])
                    minute = int(time_parts[1])
                    second = int(time_parts[2]) if len(time_parts) > 2 else 0
                    check_in_time = time(hour, minute, second)
                
                if period.get('checkOutTime'):
                    time_parts = period['checkOutTime'].split(':')
                    hour = int(time_parts[0])
                    minute = int(time_parts[1])
                    second = int(time_parts[2]) if len(time_parts) > 2 else 0
                    check_out_time = time(hour, minute, second)
                
                # إنشاء سجل حضور جديد
                attendance = Attendance(
                    empId=empId,
                    checkInTime=check_in_time,
                    checkOutTime=check_out_time,
                    checkInReason=period.get('checkInReason'),
                    checkOutReason=period.get('checkOutReason'),
                    createdAt=datetime.combine(target_date, check_in_time) if check_in_time else datetime.now()
                )
                
                db.session.add(attendance)
                created_records.append({
                    'checkInTime': str(check_in_time) if check_in_time else None,
                    'checkOutTime': str(check_out_time) if check_out_time else None,
                    'checkInReason': period.get('checkInReason'),
                    'checkOutReason': period.get('checkOutReason')
                })
                
            except (ValueError, IndexError) as e:
                db.session.rollback()
                return jsonify({
                    'status': 'error',
                    'message': f'Invalid time format in period {i + 1}: {str(e)}'
                }), 400
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': f'Successfully updated {len(created_records)} attendance periods for {employee.full_name}',
            'data': {
                'employee_id': empId,
                'employee_name': employee.full_name,
                'date': date_str,
                'periods_count': len(created_records),
                'periods': created_records
            }
        }), 200
        
    except ValueError:
        return jsonify({
            'status': 'error',
            'message': 'Invalid date format. Please use YYYY-MM-DD'
        }), 400
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': f'Error updating attendance periods: {str(e)}'
        }), 500


@attendance_bp.route('/api/attendances', methods=['POST'])
@token_required
def create_attendance_with_custom_date(user_id):
    """
    إنشاء سجل حضور جديد مع إمكانية تحديد التاريخ
    """
    try:
        data = request.get_json()

        # التحقق من الحقول المطلوبة
        if 'empId' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Employee ID is required'
            }), 400

        # التحقق من وجود الموظف
        employee = Employee.query.get(data['empId'])
        if not employee:
            return jsonify({
                'status': 'error',
                'message': 'Employee not found'
            }), 404

        # تحديد التاريخ - إما من البيانات المرسلة أو التاريخ الحالي
        if 'customDate' in data and data['customDate']:
            try:
                target_date = datetime.strptime(data['customDate'], '%Y-%m-%d').date()
                created_at = datetime.combine(target_date, datetime.now().time())
            except ValueError:
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid date format. Please use YYYY-MM-DD'
                }), 400
        else:
            created_at = datetime.now()

        # تحويل أوقات الدخول والخروج
        check_in_time = None
        check_out_time = None

        if 'checkInTime' in data and data['checkInTime']:
            try:
                time_parts = data['checkInTime'].split(':')
                hour = int(time_parts[0])
                minute = int(time_parts[1])
                second = int(time_parts[2]) if len(time_parts) > 2 else 0
                check_in_time = time(hour, minute, second)
            except (ValueError, IndexError):
                check_in_time = datetime.now().time()

        if 'checkOutTime' in data and data['checkOutTime']:
            try:
                time_parts = data['checkOutTime'].split(':')
                hour = int(time_parts[0])
                minute = int(time_parts[1])
                second = int(time_parts[2]) if len(time_parts) > 2 else 0
                check_out_time = time(hour, minute, second)
            except (ValueError, IndexError):
                check_out_time = None

        # إنشاء سجل الحضور
        attendance = Attendance(
            empId=data['empId'],
            checkInTime=check_in_time,
            checkOutTime=check_out_time,
            checkInReason=data.get('checkInReason'),
            checkOutReason=data.get('checkOutReason'),
            createdAt=created_at
        )

        db.session.add(attendance)
        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'Attendance record created successfully',
            'data': {
                'id': attendance.id,
                'empId': attendance.empId,
                'employee_name': employee.full_name,
                'checkInTime': str(attendance.checkInTime) if attendance.checkInTime else None,
                'checkOutTime': str(attendance.checkOutTime) if attendance.checkOutTime else None,
                'checkInReason': attendance.checkInReason,
                'checkOutReason': attendance.checkOutReason,
                'createdAt': str(attendance.createdAt)
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': f'Error creating attendance record: {str(e)}'
        }), 500


@attendance_bp.route('/api/attendances/employee/<int:empId>/validate-periods', methods=['POST'])
@token_required
def validate_attendance_periods(user_id, empId):
    """
    التحقق من صحة فترات الحضور قبل الحفظ
    """
    try:
        data = request.get_json()
        periods = data.get('periods', [])
        date_str = data.get('date')

        if not periods:
            return jsonify({
                'status': 'error',
                'message': 'No periods provided for validation'
            }), 400

        validation_errors = []

        # التحقق من كل فترة
        for i, period in enumerate(periods):
            period_errors = []

            # التحقق من وجود وقت الدخول
            if not period.get('checkInTime'):
                period_errors.append('وقت الدخول مطلوب')

            # التحقق من أن وقت الخروج بعد وقت الدخول
            if period.get('checkInTime') and period.get('checkOutTime'):
                try:
                    check_in_parts = period['checkInTime'].split(':')
                    check_out_parts = period['checkOutTime'].split(':')
                    
                    check_in_seconds = int(check_in_parts[0]) * 3600 + int(check_in_parts[1]) * 60 + int(check_in_parts[2] if len(check_in_parts) > 2 else 0)
                    check_out_seconds = int(check_out_parts[0]) * 3600 + int(check_out_parts[1]) * 60 + int(check_out_parts[2] if len(check_out_parts) > 2 else 0)
                    
                    if check_out_seconds <= check_in_seconds:
                        period_errors.append('وقت الخروج يجب أن يكون بعد وقت الدخول')
                        
                except (ValueError, IndexError):
                    period_errors.append('تنسيق الوقت غير صحيح')

            if period_errors:
                validation_errors.append({
                    'period_index': i + 1,
                    'errors': period_errors
                })

        # التحقق من تداخل الفترات
        for i in range(len(periods)):
            for j in range(i + 1, len(periods)):
                if periods_overlap(periods[i], periods[j]):
                    validation_errors.append({
                        'period_index': f'{i + 1} و {j + 1}',
                        'errors': ['تداخل بين الفترات']
                    })

        if validation_errors:
            return jsonify({
                'status': 'validation_failed',
                'message': 'Validation errors found',
                'errors': validation_errors
            }), 400

        return jsonify({
            'status': 'success',
            'message': 'All periods are valid'
        }), 200

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error validating periods: {str(e)}'
        }), 500


def periods_overlap(period1, period2):
    """
    التحقق من تداخل فترتين
    """
    try:
        # تحويل أوقات النص إلى ثواني
        def time_to_seconds(time_str):
            if not time_str:
                return None
            parts = time_str.split(':')
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2] if len(parts) > 2 else 0)

        p1_start = time_to_seconds(period1.get('checkInTime'))
        p1_end = time_to_seconds(period1.get('checkOutTime'))
        
        p2_start = time_to_seconds(period2.get('checkInTime'))
        p2_end = time_to_seconds(period2.get('checkOutTime'))

        if not all([p1_start, p1_end, p2_start, p2_end]):
            return False

        # تحقق من التداخل
        return (p1_start < p2_end and p2_start < p1_end)

    except (ValueError, TypeError):
        return False