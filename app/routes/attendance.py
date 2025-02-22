from datetime import datetime, timedelta
from flask import Blueprint, json, request, jsonify
from sqlalchemy import func ,cast, Date
from app import db
from app.models import Attendance, Employee, Shift
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


# Get All Attendances
@attendance_bp.route('/api/attendances', methods=['GET'])
@token_required
def get_all_attendances(user_id):
    attendances = Attendance.query.all()
    return jsonify([{
        'id': att.id,
        'empId': att.empId,
        'checkInTime': str(att.checkInTime),
        'checkOutTime': str(att.checkOutTime) if att.checkOutTime else None,
        'createdAt': str(att.createdAt)
    } for att in attendances]), 200


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

# Check-in Attendance for Employee
@attendance_bp.route('/api/attendances/checkin', methods=['POST'])
@token_required
def check_in(user_id):
    try:
        data = request.get_json()

        # Validate required fields
        if 'empId' not in data:
            return jsonify({'message': 'Employee ID is required'}), 400

        # Get employee from empId
        employee = Employee.query.get(data['empId'])
        if not employee:
            return jsonify({'message': 'Employee not found'}), 404

        # التحقق من عدم وجود تسجيل دخول لنفس اليوم
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        existing_attendance = Attendance.query.filter(
            Attendance.empId == data['empId'],
            Attendance.createdAt >= today_start,
            Attendance.createdAt < today_end
        ).first()

        # معالجة وقت تسجيل الدخول
        check_in_time_str = data.get('checkInTime')
        if check_in_time_str:
            try:
                check_in_time = datetime.strptime(check_in_time_str, '%H:%M:%S').time()
            except ValueError:
                return jsonify({'message': 'Invalid time format, expected HH:mm:ss'}), 400
        else:
            check_in_time = datetime.now().time()

        # إنشاء سجل الحضور
        attendance = Attendance(
            empId=data['empId'],
            checkInTime=check_in_time,
            checkOutTime=None
        )
        
        db.session.add(attendance)
        db.session.commit()

        response_data = {
            'message': 'Check-in successful',
            'attendance': {
                'id': attendance.id,
                'empId': attendance.empId,
                'createdAt': str(attendance.createdAt),
                'checkInTime': str(attendance.checkInTime),
                'employee': {
                    'id': employee.id,
                    'full_name': employee.full_name
                }
            }
        }

        return jsonify(response_data), 201

    except Exception as e:
        db.session.rollback()
        print(f"Check-in error: {str(e)}")
        return jsonify({
            'message': 'Error processing check-in',
            'error': str(e)
        }), 500
      
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

    # Get current time for check-out
    check_out_time = datetime.now().time()

    # Update check-out time
    latest_attendance.checkOutTime = check_out_time

    db.session.commit()

    return jsonify({
        'message': 'Check-out time set successfully',
        'attendance': {
            'id': latest_attendance.id,
            'empId': latest_attendance.empId,
            'createdAt': str(latest_attendance.createdAt),
            'checkInTime': str(latest_attendance.checkInTime),
            'checkOutTime': str(latest_attendance.checkOutTime),
        }
    }), 200


# @attendance_bp.route('/api/attendances/summary', methods=['GET'])
# @token_required
# def get_all_attendance_summary(user_id):
#     date_str = request.args.get('startDate')  # Format: YYYY-MM-DD
#     if not date_str:
#         return jsonify({'message': 'Date parameter is required'}), 400

#     try:
#         target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
#     except ValueError:
#         return jsonify({'message': 'Invalid date format. Please use YYYY-MM-DD'}), 400

#     attendances = Attendance.query.filter(
#         Attendance.createdAt == target_date
#     ).all()

#     if not attendances:
#         return jsonify({'message': 'No attendance records found for the given date'})

#     result = []

#     for emp_id in set(att.empId for att in attendances):  # Get unique employee IDs
#         employee_attendances = [att for att in attendances if att.empId == emp_id]

#         employee = employee_attendances[0].employee  # Use relationship to fetch employee data

#         shift = Shift.query.filter_by(id=employee.shift_id).first()  # Fetch shift data
#         if not shift:
#             continue  

#         first_check_in = min(att.checkInTime for att in employee_attendances)
#         last_check_out = max(
#             (att.checkOutTime for att in employee_attendances if att.checkOutTime), 
#             default=None
#         )

#         # Calculate actual check-in and check-out times considering allowed delay/exit
#         allowed_delay = timedelta(minutes=shift.allowed_delay_minutes)
#         allowed_exit = timedelta(minutes=shift.allowed_exit_minutes)

#         shift_start_time = time_to_seconds(shift.start_time)
#         shift_end_time = time_to_seconds(shift.end_time)

#         first_check_in_seconds = time_to_seconds(first_check_in)
#         last_check_out_seconds = time_to_seconds(last_check_out) if last_check_out else None

#         # Determine actual check-in time
#         if first_check_in_seconds <= shift_start_time + allowed_delay.total_seconds():
#             actual_check_in_time = shift.start_time
#             check_in_status = "On Time"
#         else:
#             actual_check_in_time = first_check_in
#             check_in_status = "Late"

#         # Determine actual check-out time
#         if last_check_out:
#             if last_check_out_seconds >= shift_end_time - allowed_exit.total_seconds():
#                 actual_check_out_time = shift.end_time
#                 check_out_status = "On Time"
#             else:
#                 actual_check_out_time = last_check_out
#                 check_out_status = "Early"
#         else:
#             actual_check_out_time = None
#             check_out_status = "No Check-out"

#         # Calculate total work time based on each check-in and check-out period
#         total_work_time = timedelta()
#         total_break_time = timedelta()

#         for attendance in employee_attendances:
#             if attendance.checkInTime and attendance.checkOutTime:
#                 # Calculate work time for each period
#                 work_time_seconds = time_to_seconds(attendance.checkOutTime) - time_to_seconds(attendance.checkInTime)
#                 total_work_time += timedelta(seconds=work_time_seconds)

#         # Calculate break time between attendance periods
#         for i in range(1, len(employee_attendances)):
#             if employee_attendances[i].checkInTime and employee_attendances[i - 1].checkOutTime:
#                 check_in_seconds = time_to_seconds(employee_attendances[i].checkInTime)
#                 check_out_seconds = time_to_seconds(employee_attendances[i - 1].checkOutTime)

#                 # Calculate break time between periods
#                 break_time_seconds = check_in_seconds - check_out_seconds
#                 total_break_time += timedelta(seconds=break_time_seconds)

#         # Format total break time and work time
#         total_break_hours, remainder_break = divmod(total_break_time.seconds, 3600)
#         total_break_minutes = remainder_break // 60

#         total_work_hours, remainder_work = divmod(total_work_time.seconds, 3600)
#         total_work_minutes = remainder_work // 60

#         # Determine the next required action for the employee
#         last_attendance = max(employee_attendances, key=lambda att: att.id)
#         if last_attendance.checkInTime and not last_attendance.checkOutTime:
#             next_action = "check-out"  # Employee should check out
#         else:
#             next_action = "check-in"  # Employee should check in

#         # Create attendance periods
#         attendance_periods = []
#         for att in employee_attendances:
#             attendance_periods.append({
#                 'checkInTime': str(att.checkInTime),
#                 'checkOutTime': str(att.checkOutTime) if att.checkOutTime else None
#             })

#         # Add detailed employee data to the result
#         result.append({
#             'employee': {
#                 'id': employee.id,
#                 'name': employee.full_name,
#                 'work_system': employee.work_system
#             },
#             'date': date_str,
#             'actualCheckIn': str(actual_check_in_time),
#             'checkInStatus': check_in_status,
#             'actualCheckOut': str(actual_check_out_time) if actual_check_out_time else None,
#             'checkOutStatus': check_out_status,
#             'totalBreakTime': f"{total_break_hours} hours {total_break_minutes} minutes",
#             'totalWorkTime': f"{total_work_hours} hours {total_work_minutes} minutes",
#             'nextAction': next_action,
#             'attendancePeriods': attendance_periods,
#             'firstCheckIn': str(first_check_in), 
#             'lastCheckOut': str(last_check_out) if last_check_out else None 
#         })

#     return jsonify(result), 200

@attendance_bp.route('/api/attendances/summary', methods=['GET'])
@token_required
def get_all_attendance_summary(user_id):
    date_str = request.args.get('startDate')
    if not date_str:
        return jsonify({'message': 'Date parameter is required'}), 400

    try:
        # تحويل التاريخ المدخل إلى كائن تاريخ
        target_date = datetime.strptime(date_str, '%Y-%m-%d')
        
        # إنشاء نطاق زمني لليوم المحدد
        start_datetime = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_datetime = (start_datetime + timedelta(days=1))

        # الحصول على سجلات الحضور لليوم المحدد
        attendances = Attendance.query.filter(
            Attendance.createdAt >= start_datetime,
            Attendance.createdAt < end_datetime
        ).all()

        if not attendances:
            return jsonify({'message': 'No attendance records found for the given date'})

        result = []

        for emp_id in set(att.empId for att in attendances):
            employee_attendances = [att for att in attendances if att.empId == emp_id]
            employee = employee_attendances[0].employee

            # تحديد نظام العمل للموظف
            if employee.work_system == 'shift':
                # منطق معالجة نظام الورديات
                attendance_summary = process_shift_attendance(employee, employee_attendances, date_str)
                if attendance_summary:
                    result.append(attendance_summary)
            else:
                # منطق معالجة نظام الساعات
                attendance_summary = process_hours_attendance(employee, employee_attendances, date_str)
                if attendance_summary:
                    result.append(attendance_summary)

        return jsonify(result), 200

    except ValueError:
        return jsonify({'message': 'Invalid date format. Please use YYYY-MM-DD'}), 400
    except Exception as e:
        print(f"Error processing attendance summary: {str(e)}")
        return jsonify({'message': 'Error processing attendance records', 'error': str(e)}), 500


def process_shift_attendance(employee, employee_attendances, date_str):
    """معالجة حضور الموظف في نظام الورديات"""
    shift = Shift.query.filter_by(id=employee.shift_id).first()
    if not shift:
        return None

    first_check_in = min(att.checkInTime for att in employee_attendances)
    last_check_out = max(
        (att.checkOutTime for att in employee_attendances if att.checkOutTime),
        default=None
    )

    # حساب أوقات الحضور والانصراف الفعلية مع مراعاة التأخير المسموح به
    allowed_delay = timedelta(minutes=shift.allowed_delay_minutes)
    allowed_exit = timedelta(minutes=shift.allowed_exit_minutes)

    shift_start_time = time_to_seconds(shift.start_time)
    shift_end_time = time_to_seconds(shift.end_time)
    first_check_in_seconds = time_to_seconds(first_check_in)
    last_check_out_seconds = time_to_seconds(last_check_out) if last_check_out else None

    # حساب حالة الحضور
    if first_check_in_seconds <= shift_start_time + allowed_delay.total_seconds():
        actual_check_in_time = shift.start_time
        check_in_status = "On Time"
    else:
        actual_check_in_time = first_check_in
        check_in_status = "Late"

    # حساب حالة الانصراف
    if last_check_out:
        if last_check_out_seconds >= shift_end_time - allowed_exit.total_seconds():
            actual_check_out_time = shift.end_time
            check_out_status = "On Time"
        else:
            actual_check_out_time = last_check_out
            check_out_status = "Early"
    else:
        actual_check_out_time = None
        check_out_status = "No Check-out"

    # حساب إجمالي وقت العمل والاستراحة
    total_work_time, total_break_time = calculate_work_and_break_time(employee_attendances)

    return format_attendance_summary(
        employee, date_str, actual_check_in_time, check_in_status,
        actual_check_out_time, check_out_status, total_work_time,
        total_break_time, employee_attendances
    )

def process_hours_attendance(employee, employee_attendances, date_str):
    """معالجة حضور الموظف في نظام الساعات"""
    first_check_in = min(att.checkInTime for att in employee_attendances)
    last_check_out = max(
        (att.checkOutTime for att in employee_attendances if att.checkOutTime),
        default=None
    )

    # في نظام الساعات، نعتبر كل تسجيل دخول وخروج كفترة عمل منفصلة
    total_work_time, total_break_time = calculate_work_and_break_time(employee_attendances)

    # لا نحتاج لحساب التأخير في نظام الساعات
    check_in_status = "Recorded"
    check_out_status = "Recorded" if last_check_out else "No Check-out"

    return format_attendance_summary(
        employee, date_str, first_check_in, check_in_status,
        last_check_out, check_out_status, total_work_time,
        total_break_time, employee_attendances
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
        'checkOutTime': str(att.checkOutTime) if att.checkOutTime else None
    } for att in employee_attendances]

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

    # إضافة بيانات المسمى الوظيفي إذا كان موظفاً دائماً
    if employee.job_title:
        employee_data['job_title'] = {
            'id': employee.job_title.id,
            'title_name': employee.job_title.title_name
        }

    # إضافة بيانات المهنة إذا كان موظفاً مؤقتاً
    if employee.profession:
        employee_data['profession'] = {
            'id': employee.profession.id,
            'name': employee.profession.name,
            'hourly_rate': float(employee.profession.hourly_rate),
            'daily_rate': float(employee.profession.daily_rate)
        }

    # تجميع النتيجة النهائية
    return {
        'employee': employee_data,
        'date': date_str,
        'actualCheckIn': str(check_in_time),
        'checkInStatus': check_in_status,
        'actualCheckOut': str(check_out_time) if check_out_time else None,
        'checkOutStatus': check_out_status,
        'totalWorkTime': f"{total_work_hours} hours {total_work_minutes} minutes",
        'totalBreakTime': f"{total_break_hours} hours {total_break_minutes} minutes",
        'nextAction': next_action,
        'attendancePeriods': attendance_periods,
        'firstCheckIn': str(check_in_time),
        'lastCheckOut': str(check_out_time) if check_out_time else None
    }

def time_to_seconds(t):
    """Convert a time object to seconds since midnight."""
    return t.hour * 3600 + t.minute * 60 + t.second