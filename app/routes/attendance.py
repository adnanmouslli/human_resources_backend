from datetime import datetime, time, timedelta
from flask import Blueprint, json, request, jsonify
from sqlalchemy import func ,cast, Date
from app import db
from app.models import Attendance, Employee, Shift
from app.models.holiday import Holiday
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

    # تحديد التاريخ المستهدف - إما من البيانات المرسلة أو اليوم الحالي
    target_date = datetime.now().date()  # القيمة الافتراضية
    
    if 'date' in data and data['date']:
        try:
            # تحويل التاريخ المرسل من نص إلى كائن date
            target_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'message': 'Invalid date format. Use YYYY-MM-DD'}), 400

    # استخدام وقت حضور مخصص إذا تم تقديمه، وإلا استخدام الوقت الحالي
    if 'checkInTime' in data and data['checkInTime']:
        try:
            # تحويل النص إلى كائن time
            time_parts = data['checkInTime'].split(':')
            hour = int(time_parts[0])
            minute = int(time_parts[1])
            second = int(time_parts[2]) if len(time_parts) > 2 else 0
            
            # التحقق من صحة القيم
            if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
                return jsonify({'message': 'Invalid time format'}), 400
                
            check_in_time = time(hour, minute, second)
        except (ValueError, IndexError):
            return jsonify({'message': 'Invalid checkInTime format. Use HH:MM:SS'}), 400
    else:
        # استخدام الوقت الحالي إذا لم يتم تقديم وقت مخصص
        check_in_time = datetime.now().time()

    # التحقق من وجود سجل حضور مفتوح في نفس التاريخ
    existing_open_attendance = (
        Attendance.query.filter(
            Attendance.empId == data['empId'],
            Attendance.checkOutTime == None,
            cast(Attendance.createdAt, Date) == target_date
        ).first()
    )
    
    if existing_open_attendance:
        formatted_date = target_date.strftime('%Y-%m-%d')
        return jsonify({
            'message': f'Employee already has an open attendance record for {formatted_date}'
        }), 400

    # إنشاء سجل حضور جديد
    new_attendance = Attendance(
        empId=data['empId'],
        createdAt=target_date,
        checkInTime=check_in_time,
        checkInReason=data.get('checkInReason', None)  # سبب الدخول اختياري
    )

    try:
        db.session.add(new_attendance)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Failed to create attendance record'}), 500

    return jsonify({
        'message': 'Check-in successful',
        'attendance': {
            'id': new_attendance.id,
            'empId': new_attendance.empId,
            'date': str(new_attendance.createdAt),
            'checkInTime': str(new_attendance.checkInTime),
            'checkOutTime': None,
            'checkInReason': new_attendance.checkInReason,
            'checkOutReason': None
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

    # تحديد التاريخ المستهدف - إما من البيانات المرسلة أو اليوم الحالي
    target_date = datetime.now().date()  # القيمة الافتراضية
    
    if 'date' in data and data['date']:
        try:
            # تحويل التاريخ المرسل من نص إلى كائن date
            target_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'message': 'Invalid date format. Use YYYY-MM-DD'}), 400

    # Get the latest attendance record for the target date without a check-out time
    latest_attendance = (
        Attendance.query.filter(
            Attendance.empId == data['empId'],
            Attendance.checkOutTime == None,
            cast(Attendance.createdAt, Date) == target_date
        )
        .order_by(Attendance.createdAt.desc(), Attendance.checkInTime.desc())
        .first()
    )
    
    if not latest_attendance:
        formatted_date = target_date.strftime('%Y-%m-%d')
        return jsonify({
            'message': f'No open attendance records found for employee on {formatted_date}'
        }), 404

    # استخدام وقت انصراف مخصص إذا تم تقديمه، وإلا استخدام الوقت الحالي
    if 'checkOutTime' in data and data['checkOutTime']:
        try:
            # تحويل النص إلى كائن time
            time_parts = data['checkOutTime'].split(':')
            hour = int(time_parts[0])
            minute = int(time_parts[1])
            second = int(time_parts[2]) if len(time_parts) > 2 else 0
            
            # التحقق من صحة القيم
            if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
                return jsonify({'message': 'Invalid time format'}), 400
                
            check_out_time = time(hour, minute, second)
        except (ValueError, IndexError):
            return jsonify({'message': 'Invalid checkOutTime format. Use HH:MM:SS'}), 400
    else:
        # استخدام الوقت الحالي إذا لم يتم تقديم وقت مخصص
        check_out_time = datetime.now().time()

    # التحقق من أن وقت الخروج ليس قبل وقت الدخول (في نفس اليوم)
    if check_out_time < latest_attendance.checkInTime:
        # في حالة الخروج في اليوم التالي، هذا مقبول
        # لكن إذا كان في نفس اليوم، فهذا خطأ
        if target_date == latest_attendance.createdAt:
            return jsonify({
                'message': 'Check-out time cannot be earlier than check-in time on the same day'
            }), 400

    # Update check-out time and reason
    latest_attendance.checkOutTime = check_out_time
    
    # إضافة سبب الخروج إذا تم تقديمه
    if 'checkOutReason' in data and data['checkOutReason']:
        latest_attendance.checkOutReason = data['checkOutReason']
    
    # إضافة كمية الإنتاج إذا تم تقديمها (للموظفين الذين يعملون بنظام الإنتاجية)
    if 'productionQuantity' in data and data['productionQuantity'] is not None:
        latest_attendance.productionQuantity = float(data['productionQuantity'])
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Failed to update attendance record'}), 500

    return jsonify({
        'message': 'Check-out time set successfully',
        'attendance': {
            'id': latest_attendance.id,
            'empId': latest_attendance.empId,
            'date': str(latest_attendance.createdAt),
            'checkInTime': str(latest_attendance.checkInTime),
            'checkOutTime': str(latest_attendance.checkOutTime),
            'checkInReason': latest_attendance.checkInReason,
            'checkOutReason': latest_attendance.checkOutReason,
            'productionQuantity': latest_attendance.productionQuantity
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

def sync_fingerprint_records():
    """
    مزامنة سجلات البصمة المحسّنة مع معالجة جميع السيناريوهات:
    1. إضافة سجلات جديدة
    2. تحديث سجلات موجودة (إضافة خروج لسجل دخول موجود)
    3. معالجة بصمات متعددة في نفس اليوم
    4. تجنب المزامنة المتكررة للبيانات نفسها
    """
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
            'updated': 0,
            'failed': 0,
            'skipped': 0,
            'employees_processed': 0,
            'days_processed': 0,
            'details': [],
            'processing_summary': []
        }
        
        # تجميع السجلات حسب الموظف والتاريخ
        employee_date_records = {}
        
        print(f"بدء معالجة {len(records)} سجل")
        
        # المرحلة 1: معالجة السجلات الخام وتجميعها
        for i, record in enumerate(records):
            try:
                print(f"معالجة السجل {i+1}: {record}")
                
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
                
                # البحث عن الموظف
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
                
                # تحويل الطابع الزمني
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
                
                # تجميع البصمات
                if employee.id not in employee_date_records:
                    employee_date_records[employee.id] = {}
                
                if date_key not in employee_date_records[employee.id]:
                    employee_date_records[employee.id][date_key] = {
                        'employee': employee,
                        'date': record_date,
                        'fingerprint_id': fingerprint_id,
                        'timestamps': []
                    }
                
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
        
        # المرحلة 2: معالجة البصمات بذكاء
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
                    
                    # البحث عن السجل الموجود لهذا الموظف في هذا اليوم
                    existing_attendance = Attendance.query.filter(
                        Attendance.empId == emp_id,
                        cast(Attendance.createdAt, Date) == record_date
                    ).first()
                    
                    # استخراج أول وآخر بصمة
                    first_timestamp = timestamps[0]
                    last_timestamp = timestamps[-1] if len(timestamps) > 1 else None
                    
                    # تحديد أوقات الدخول والخروج
                    check_in_time = first_timestamp['time'].time()
                    check_in_datetime = first_timestamp['time']
                    check_out_time = None
                    check_out_datetime = None
                    
                    if last_timestamp and len(timestamps) > 1:
                        time_diff = (last_timestamp['time'] - first_timestamp['time']).total_seconds()
                        if time_diff > 300:  # أكثر من 5 دقائق
                            check_out_time = last_timestamp['time'].time()
                            check_out_datetime = last_timestamp['time']
                    
                    # معالجة السيناريوهات المختلفة
                    if existing_attendance is None:
                        # السيناريو 1: لا يوجد سجل سابق - إنشاء سجل جديد
                        attendance = Attendance(
                            empId=employee.id,
                            checkInTime=check_in_time,
                            createdAt=check_in_datetime,
                            checkInReason=f'Fingerprint sync - first of {len(timestamps)} records',
                            checkOutTime=check_out_time,
                            checkOutReason=f'Fingerprint sync - last of {len(timestamps)} records' if check_out_time else None
                        )
                        
                        db.session.add(attendance)
                        results['success'] += 1
                        action = 'created'
                        
                        print(f"✓ تم إنشاء سجل جديد للموظف {employee_name}")
                        
                    else:
                        # السيناريو 2: يوجد سجل سابق
                        action = 'no_change'
                        
                        # فحص ما إذا كنا بحاجة للتحديث
                        need_update = False
                        update_reasons = []
                        
                        # التحقق من وقت الدخول - القاعدة: دائماً أقدم وقت دخول
                        if existing_attendance.checkInTime != check_in_time:
                            # مقارنة أوقات الدخول - نأخذ الأقدم دائماً
                            existing_check_in_datetime = datetime.combine(record_date, existing_attendance.checkInTime)
                            
                            if check_in_datetime < existing_check_in_datetime:
                                # الوقت الجديد أقدم - نحديث
                                old_time = existing_attendance.checkInTime.strftime("%H:%M:%S")
                                existing_attendance.checkInTime = check_in_time
                                existing_attendance.createdAt = check_in_datetime
                                existing_attendance.checkInReason = f'Fingerprint sync - checkin updated to earliest time from {len(timestamps)} records'
                                need_update = True
                                update_reasons.append(f'تحديث وقت الدخول إلى الأقدم: من {old_time} إلى {check_in_time.strftime("%H:%M:%S")}')
                            elif check_in_datetime > existing_check_in_datetime:
                                # الوقت الجديد أحدث - نبقي على الموجود الأقدم
                                print(f"  - تم تجاهل وقت دخول أحدث للموظف {employee_name}: الجديد {check_in_time.strftime('%H:%M:%S')} > الموجود {existing_attendance.checkInTime.strftime('%H:%M:%S')}")
                            else:
                                # نفس الوقت - لا حاجة للتحديث
                                print(f"  - وقت الدخول مطابق للموجود للموظف {employee_name}: {check_in_time.strftime('%H:%M:%S')}")
                        
                        # التحقق من وقت الخروج - القاعدة: دائماً آخر وقت خروج
                        if check_out_time is not None:
                            if existing_attendance.checkOutTime is None:
                                # إضافة وقت خروج جديد
                                existing_attendance.checkOutTime = check_out_time
                                existing_attendance.checkOutReason = f'Fingerprint sync - checkout added from {len(timestamps)} records'
                                need_update = True
                                update_reasons.append(f'إضافة وقت الخروج: {check_out_time.strftime("%H:%M:%S")}')
                            elif existing_attendance.checkOutTime != check_out_time:
                                # مقارنة أوقات الخروج - نأخذ الأحدث دائماً
                                existing_check_out_datetime = datetime.combine(record_date, existing_attendance.checkOutTime)
                                
                                if check_out_datetime > existing_check_out_datetime:
                                    # الوقت الجديد أحدث - نحديث
                                    old_time = existing_attendance.checkOutTime.strftime("%H:%M:%S")
                                    existing_attendance.checkOutTime = check_out_time
                                    existing_attendance.checkOutReason = f'Fingerprint sync - checkout updated to latest time from {len(timestamps)} records'
                                    need_update = True
                                    update_reasons.append(f'تحديث وقت الخروج إلى الأحدث: من {old_time} إلى {check_out_time.strftime("%H:%M:%S")}')
                                elif check_out_datetime < existing_check_out_datetime:
                                    # الوقت الجديد أقدم - نبقي على الموجود الأحدث
                                    print(f"  - تم تجاهل وقت خروج أقدم للموظف {employee_name}: الجديد {check_out_time.strftime('%H:%M:%S')} < الموجود {existing_attendance.checkOutTime.strftime('%H:%M:%S')}")
                                else:
                                    # نفس الوقت - لا حاجة للتحديث
                                    print(f"  - وقت الخروج مطابق للموجود للموظف {employee_name}: {check_out_time.strftime('%H:%M:%S')}")
                        
                        if need_update:
                            results['updated'] += 1
                            action = 'updated'
                            print(f"✓ تم تحديث سجل الموظف {employee_name}: {', '.join(update_reasons)}")
                        else:
                            results['skipped'] += 1
                            action = 'skipped'
                            print(f"- تم تجاهل سجل الموظف {employee_name}: لا توجد تحديثات مطلوبة")
                    
                    # إضافة تفاصيل العملية
                    processing_info = {
                        'employee_id': employee.id,
                        'employee_name': employee.full_name,
                        'fingerprint_id': fingerprint_id,
                        'date': date_key,
                        'action': action,
                        'status': 'success',
                        'total_fingerprints': len(timestamps),
                        'check_in_time': check_in_time.strftime("%H:%M:%S"),
                        'check_out_time': check_out_time.strftime("%H:%M:%S") if check_out_time else None,
                        'all_timestamps': [ts['time'].strftime("%H:%M:%S") for ts in timestamps],
                        'had_existing_record': existing_attendance is not None
                    }
                    
                    results['processing_summary'].append(processing_info)
                    
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
        
        # إعداد رسالة النجاح
        success_message = f'تمت معالجة سجلات الحضور: '
        success_message += f'{results["success"]} سجل جديد، '
        success_message += f'{results["updated"]} سجل محدث، '
        success_message += f'{results["skipped"]} سجل تم تجاهله، '
        success_message += f'{results["failed"]} فشل، '
        success_message += f'{results["employees_processed"]} موظف، '
        success_message += f'{results["days_processed"]} يوم'
        
        print("انتهاء المعالجة بنجاح")
        print(f"الملخص: {success_message}")
        
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




@attendance_bp.route('/api/attendance/test-scenarios', methods=['POST'])
def test_sync_scenarios():
    """
    API endpoint لاختبار سيناريوهات مختلفة للمزامنة
    يساعد في فهم كيفية عمل النظام مع حالات مختلفة
    """
    try:
        # سيناريوهات الاختبار
        test_scenarios = [
            {
                'name': 'سجل جديد كامل - دخول وخروج',
                'description': 'إنشاء سجل جديد مع وقت دخول وخروج',
                'existing_record': None,
                'new_timestamps': ['08:00:00', '17:00:00'],
                'expected_result': 'إنشاء سجل جديد: دخول 08:00:00، خروج 17:00:00'
            },
            {
                'name': 'سجل جديد - دخول فقط',
                'description': 'إنشاء سجل جديد مع وقت دخول فقط',
                'existing_record': None,
                'new_timestamps': ['08:30:00'],
                'expected_result': 'إنشاء سجل جديد: دخول 08:30:00، بدون خروج'
            },
            {
                'name': 'إضافة خروج لسجل موجود',
                'description': 'سجل موجود بدون خروج + مزامنة مع خروج',
                'existing_record': {'check_in': '08:00:00', 'check_out': None},
                'new_timestamps': ['08:00:00', '17:30:00'],
                'expected_result': 'تحديث السجل: إضافة خروج 17:30:00'
            },
            {
                'name': 'تحديث خروج إلى وقت أحدث',
                'description': 'سجل كامل + مزامنة مع خروج أحدث',
                'existing_record': {'check_in': '08:00:00', 'check_out': '17:00:00'},
                'new_timestamps': ['08:00:00', '18:00:00'],
                'expected_result': 'تحديث الخروج من 17:00:00 إلى 18:00:00'
            },
            {
                'name': 'تجاهل خروج أقدم',
                'description': 'سجل كامل + مزامنة مع خروج أقدم',
                'existing_record': {'check_in': '08:00:00', 'check_out': '18:00:00'},
                'new_timestamps': ['08:00:00', '17:00:00'],
                'expected_result': 'تجاهل الخروج الأقدم، الاحتفاظ بـ 18:00:00'
            },
            {
                'name': 'تحديث دخول إلى وقت أقدم',
                'description': 'سجل كامل + مزامنة مع دخول أقدم',
                'existing_record': {'check_in': '08:30:00', 'check_out': '17:00:00'},
                'new_timestamps': ['08:00:00', '17:00:00'],
                'expected_result': 'تحديث الدخول من 08:30:00 إلى 08:00:00'
            },
            {
                'name': 'تجاهل دخول أحدث',
                'description': 'سجل كامل + مزامنة مع دخول أحدث',
                'existing_record': {'check_in': '08:00:00', 'check_out': '17:00:00'},
                'new_timestamps': ['08:30:00', '17:00:00'],
                'expected_result': 'تجاهل الدخول الأحدث، الاحتفاظ بـ 08:00:00'
            },
            {
                'name': 'تحديث كامل - دخول أقدم وخروج أحدث',
                'description': 'سجل كامل + مزامنة مع تحسينات في الوقتين',
                'existing_record': {'check_in': '08:30:00', 'check_out': '17:00:00'},
                'new_timestamps': ['08:00:00', '18:00:00'],
                'expected_result': 'تحديث الدخول إلى 08:00:00 والخروج إلى 18:00:00'
            },
            {
                'name': 'مزامنة متطابقة',
                'description': 'سجل كامل + مزامنة بنفس الأوقات',
                'existing_record': {'check_in': '08:00:00', 'check_out': '17:00:00'},
                'new_timestamps': ['08:00:00', '17:00:00'],
                'expected_result': 'تجاهل المزامنة - لا توجد تحديثات مطلوبة'
            }
        ]
        
        return jsonify({
            'status': 'success',
            'message': 'سيناريوهات الاختبار لنظام المزامنة',
            'scenarios': test_scenarios,
            'rules': {
                'check_in_rule': 'دائماً أقدم وقت دخول',
                'check_out_rule': 'دائماً أحدث وقت خروج',
                'minimum_time_diff': '5 دقائق بين الدخول والخروج'
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'خطأ في إنشاء سيناريوهات الاختبار: {str(e)}'
        }), 500



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



@attendance_bp.route('/api/attendances/summary', methods=['GET'])
@token_required
def get_all_attendance_summary_updated(current_user):
    """
    جلب ملخص حضور الموظفين مع تطبيق صلاحيات المستخدم
    - super_admin: يمكنه الوصول لجميع الموظفين
    - branch_head/branch_deputy: يمكنه الوصول لموظفي الفرع
    - department_head/department_deputy: يمكنه الوصول لموظفي القسم
    - employee: يمكنه الوصول لبياناته فقط
    """
    date_str = request.args.get('startDate')
    branch_id = request.args.get('branch_id', type=int)
    department_id = request.args.get('department_id', type=int)
    shift_id = request.args.get('shift_id', type=int)
    filter_incomplete = request.args.get('incomplete', type=int)

    

    if not date_str:
        return jsonify({'message': 'Date parameter is required'}), 400

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d')
        start_datetime = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_datetime = start_datetime + timedelta(days=1)

        # الحصول على الموظفين حسب صلاحيات المستخدم
        accessible_employees = current_user.get_accessible_employees()
        accessible_employee_ids = [emp.id for emp in accessible_employees]

        # فلترة سجلات الحضور للموظفين المسموح لهم فقط
        attendances = Attendance.query.filter(
            Attendance.createdAt >= start_datetime,
            Attendance.createdAt < end_datetime,
            Attendance.empId.in_(accessible_employee_ids)  # فلترة حسب الصلاحيات
        ).all()


        if not attendances:
            return jsonify({'message': 'No attendance records found for the given date'}), 200

        result = []

        for emp_id in set(att.empId for att in attendances):
            try:
                employee_attendances = [att for att in attendances if att.empId == emp_id]
                employee = employee_attendances[0].employee

                if not employee:
                    print(f"Employee not found for ID: {emp_id}")
                    continue

                # تطبيق الفلاتر
                if branch_id and employee.branch_id != branch_id:
                    continue
                if department_id and employee.department_id != department_id:
                    continue
                if shift_id and getattr(employee, 'shift_id', None) != shift_id:
                    continue

                # فلتر السجلات الناقصة
                if filter_incomplete:
                    total_checkins = sum(1 for a in employee_attendances if a.checkInTime is not None)
                    total_checkouts = sum(1 for a in employee_attendances if a.checkOutTime is not None)

                    if total_checkins == 0 or total_checkouts == 0 or total_checkins != total_checkouts:
                        pass
                    else:
                        continue

                # اختيار نظام الحضور حسب work_system مع النظام المحدث
                if employee.work_system == 'shift':
                    attendance_summary = process_shift_attendance_updated(employee, employee_attendances, target_date.date())
                else:
                    attendance_summary = process_hours_attendance(employee, employee_attendances, date_str)

                if attendance_summary:
                    result.append(attendance_summary)

            except Exception as emp_error:
                print(f"Error processing employee {emp_id}: {str(emp_error)}")
                continue

        return jsonify(result), 200

    except ValueError:
        return jsonify({'message': 'Invalid date format. Please use YYYY-MM-DD'}), 400
    except Exception as e:
        print(f"Error processing attendance summary: {str(e)}")
        return jsonify({'message': 'Error processing attendance records', 'error': str(e)}), 500



@attendance_bp.route('/api/attendances/raw', methods=['GET'])
@token_required
def get_raw_attendances(current_user):
    """
    جلب السجلات الخام مع الفلاتر - بدون معالجة أو دمج (بدون pagination)
    """
    try:
        # الحصول على المعاملات من الطلب (إزالة page و per_page)
        start_date = request.args.get('startDate')
        end_date = request.args.get('endDate')
        branch_id = request.args.get('branch_id', type=int)
        department_id = request.args.get('department_id', type=int)
        shift_id = request.args.get('shift_id', type=int)
        employee_id = request.args.get('employee_id', type=int)
        no_checkout = request.args.get('no_checkout', type=bool)

        # الحصول على الموظفين المسموح للمستخدم برؤيتهم
        user = User.query.get(current_user.id)
        accessible_employees = user.get_accessible_employees()
        accessible_employee_ids = [emp.id for emp in accessible_employees]

        # بناء الاستعلام الأساسي
        query = Attendance.query.filter(Attendance.empId.in_(accessible_employee_ids))

        # تطبيق الفلاتر
        if start_date:
            start_datetime = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(Attendance.createdAt >= start_datetime)

        if end_date:
            end_datetime = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(Attendance.createdAt <= end_datetime)

        # فلتر بناءً على خصائص الموظف
        if branch_id or department_id or shift_id or employee_id:
            query = query.join(Employee, Attendance.empId == Employee.id)
            
            if branch_id:
                query = query.filter(Employee.branch_id == branch_id)
            if department_id:
                query = query.filter(Employee.department_id == department_id)
            if shift_id:
                query = query.filter(Employee.shift_id == shift_id)
            if employee_id:
                query = query.filter(Employee.id == employee_id)

        # فلتر السجلات بدون خروج
        if no_checkout:
            query = query.filter(
                Attendance.checkInTime.isnot(None),
                Attendance.checkOutTime.is_(None)
            )

        # ترتيب النتائج وجلب جميع السجلات
        attendances = query.order_by(Attendance.createdAt.desc(), Attendance.checkInTime.desc()).all()

        # تجهيز البيانات للإرسال
        result = []
        for attendance in attendances:
            employee = Employee.query.get(attendance.empId)
            
            attendance_data = {
                'id': attendance.id,
                'empId': attendance.empId,
                'createdAt': attendance.createdAt.isoformat(),
                'checkInTime': attendance.checkInTime.isoformat() if attendance.checkInTime else None,
                'checkOutTime': attendance.checkOutTime.isoformat() if attendance.checkOutTime else None,
                'checkInReason': attendance.checkInReason,
                'checkOutReason': attendance.checkOutReason,
                'productionQuantity': float(attendance.productionQuantity) if attendance.productionQuantity else None,
                'employee': {
                    'id': employee.id,
                    'full_name': employee.full_name,
                    'fingerprint_id': employee.fingerprint_id,
                    'employee_type': employee.employee_type,
                    'work_system': employee.work_system,
                    'position': employee.position,
                    'branch_name': employee.branch.name if employee.branch else None,
                    'department_name': employee.department.name if employee.department else None,
                    'shift_name': None  # سنضيف هذا لاحقاً إذا لزم الأمر
                } if employee else None
            }
            
            # إضافة اسم الوردية إذا وجد
            if employee and employee.shift_id:
                shift = Shift.query.get(employee.shift_id)
                if shift:
                    attendance_data['employee']['shift_name'] = shift.name

            result.append(attendance_data)

        return jsonify({
            'status': 'success',
            'data': result,
            'total': len(result),
            'message': f'تم جلب {len(result)} سجل'
        }), 200

    except Exception as e:
        print(f"خطأ في جلب السجلات الخام: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'حدث خطأ: {str(e)}'
        }), 500
    

@attendance_bp.route('/api/attendances/<int:attendance_id>/checkout-by-id', methods=['PUT'])
@token_required
def checkout_by_attendance_id(current_user, attendance_id):
    """
    تسجيل خروج بناءً على معرف السجل
    """
    try:
        # البحث عن السجل
        attendance = Attendance.query.get(attendance_id)
        
        if not attendance:
            return jsonify({
                'status': 'error',
                'message': 'سجل الحضور غير موجود'
            }), 404

        # التحقق من عدم وجود تسجيل خروج مسبق
        if attendance.checkOutTime:
            return jsonify({
                'status': 'error',
                'message': 'تم تسجيل الخروج مسبقاً لهذا السجل'
            }), 400

        # الحصول على البيانات من الطلب
        data = request.get_json() or {}
        
        # تحديد وقت الخروج
        if 'checkOutTime' in data and data['checkOutTime']:
            try:
                time_parts = data['checkOutTime'].split(':')
                hour = int(time_parts[0])
                minute = int(time_parts[1])
                second = int(time_parts[2]) if len(time_parts) > 2 else 0
                
                if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
                    return jsonify({'message': 'تنسيق الوقت غير صحيح'}), 400
                    
                check_out_time = time(hour, minute, second)
            except (ValueError, IndexError):
                return jsonify({'message': 'تنسيق الوقت غير صحيح. استخدم HH:MM:SS'}), 400
        else:
            # استخدام الوقت الحالي
            check_out_time = datetime.now().time()

        # تحديث السجل
        attendance.checkOutTime = check_out_time
        
        if 'checkOutReason' in data:
            attendance.checkOutReason = data['checkOutReason']
        
       
        # حفظ التغييرات
        db.session.commit()

        # إعداد الرد
        employee = Employee.query.get(attendance.empId)
        
        return jsonify({
            'status': 'success',
            'message': f'تم تسجيل الخروج بنجاح للموظف {employee.full_name if employee else ""}',
            'data': {
                'id': attendance.id,
                'empId': attendance.empId,
                'employee_name': employee.full_name if employee else None,
                'createdAt': attendance.createdAt.isoformat(),
                'checkInTime': attendance.checkInTime.isoformat() if attendance.checkInTime else None,
                'checkOutTime': attendance.checkOutTime.isoformat(),
                'checkOutReason': attendance.checkOutReason,
                'productionQuantity': attendance.productionQuantity
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"خطأ في تسجيل الخروج: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'فشل في تسجيل الخروج: {str(e)}'
        }), 500


@attendance_bp.route('/api/attendances/raw/stats', methods=['GET'])
@token_required
def get_raw_attendance_stats(current_user):
    """
    الحصول على إحصائيات سريعة للسجلات الخام
    """
    try:
        start_date = request.args.get('startDate')
        end_date = request.args.get('endDate')
        
        if not start_date or not end_date:
            return jsonify({
                'status': 'error',
                'message': 'تاريخ البداية والنهاية مطلوبان'
            }), 400

        # تحويل التواريخ
        start_datetime = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_datetime = datetime.strptime(end_date, '%Y-%m-%d').date()

        # الحصول على الموظفين المسموح للمستخدم برؤيتهم
        user = User.query.get(current_user.id)
        accessible_employees = user.get_accessible_employees()
        accessible_employee_ids = [emp.id for emp in accessible_employees]

        # الاستعلام الأساسي
        base_query = Attendance.query.filter(
            Attendance.empId.in_(accessible_employee_ids),
            Attendance.createdAt >= start_datetime,
            Attendance.createdAt <= end_datetime
        )

        # حساب الإحصائيات
        total_records = base_query.count()
        records_with_checkin = base_query.filter(Attendance.checkInTime.isnot(None)).count()
        records_with_checkout = base_query.filter(Attendance.checkOutTime.isnot(None)).count()
        incomplete_records = base_query.filter(
            Attendance.checkInTime.isnot(None),
            Attendance.checkOutTime.is_(None)
        ).count()

        return jsonify({
            'status': 'success',
            'data': {
                'total_records': total_records,
                'records_with_checkin': records_with_checkin,
                'records_with_checkout': records_with_checkout,
                'incomplete_records': incomplete_records,
                'period': f'{start_date} إلى {end_date}'
            }
        }), 200

    except Exception as e:
        print(f"خطأ في حساب الإحصائيات: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'حدث خطأ: {str(e)}'
        }), 500

@attendance_bp.route('/api/attendances/filter-by-status', methods=['GET'])
@token_required
def filter_employees_by_status_updated(user_id):
    date_str = request.args.get('date')
    status_filter = request.args.get('status')

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
                    # استخدام النظام الجديد للحصول على أوقات الوردية
                    is_working_day, shift_start_time, shift_end_time = get_shift_schedule_for_date(shift, target_date)
                    
                    if is_working_day and shift_start_time:
                        shift_start_seconds = time_to_seconds(shift_start_time)
                        checkin_seconds = time_to_seconds(attendance.checkInTime)
                        delay_allowed_seconds = shift.allowed_delay_minutes * 60

                        if checkin_seconds > shift_start_seconds + delay_allowed_seconds:
                            emp_status = 'متاخر'
                        else:
                            emp_status = 'حاضر'
                    else:
                        emp_status = 'حاضر (يوم إجازة)'
                else:
                    emp_status = 'غير محدد (لا يوجد وردية)'
            else:
                emp_status = 'حاضر'
        else:
            # التحقق من كون اليوم يوم إجازة
            if employee.work_system == 'shift' and employee.shift_id:
                shift = Shift.query.get(employee.shift_id)
                if shift:
                    is_working_day, _, _ = get_shift_schedule_for_date(shift, target_date)
                    if not is_working_day:
                        emp_status = 'إجازة'
                    else:
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
        'checkOutTime': str(att.checkOutTime) if att.checkOutTime else None ,
        'checkInReason': att.checkInReason,  # إضافة سبب تسجيل الدخول
        'checkOutReason': att.checkOutReason,  # إضافة سبب تسجيل الخروج
        'attendanceId': att.id  # إضافة معرف سجل الحضور للمرجعية
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
    if t is None:
        return 0
    return t.hour * 3600 + t.minute * 60 + t.second


# تقارير الحضور الشهرية
@attendance_bp.route('/api/attendances/monthly-report', methods=['GET'])
@token_required
def get_monthly_attendance_report(user):
    """
    تقرير الحضور الشهري المفصل لجميع الموظفين
    يعرض تفاصيل الحضور لكل موظف خلال الفترة المحددة
    """
    start_date_str = request.args.get('startDate')
    end_date_str = request.args.get('endDate')
    branch_id = request.args.get('branch_id', type=int)
    department_id = request.args.get('department_id', type=int)
    shift_id = request.args.get('shift_id', type=int)
    employee_id = request.args.get('employee_id', type=int)
    
    # التحقق من وجود التواريخ المطلوبة
    if not start_date_str or not end_date_str:
        return jsonify({
            'status': 'error',
            'message': 'تاريخ البداية والنهاية مطلوبان'
        }), 400

    try:
        # تحويل التواريخ
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        
        # التحقق من صحة الفترة
        if start_date > end_date:
            return jsonify({
                'status': 'error',
                'message': 'تاريخ البداية يجب أن يكون قبل تاريخ النهاية'
            }), 400
            
        # حساب عدد الأيام
        total_days = (end_date - start_date).days + 1
        
        if total_days > 93:  # حوالي 3 أشهر
            return jsonify({
                'status': 'error',
                'message': 'الفترة المحددة طويلة جداً. الحد الأقصى 3 أشهر'
            }), 400

    except ValueError:
        return jsonify({
            'status': 'error',
            'message': 'تنسيق التاريخ غير صحيح. يجب استخدام YYYY-MM-DD'
        }), 400

    try:
        # الحصول على المستخدم وصلاحياته
        user = User.query.get(user.id)
        if not user:
            return jsonify({'status': 'error', 'message': 'المستخدم غير موجود'}), 404

        # جلب الموظفين المسموح للمستخدم برؤيتهم
        accessible_employees = user.get_accessible_employees()
        
        # تطبيق الفلاتر على الموظفين
        employees_query = accessible_employees
        
        if employee_id:
            employees_query = [emp for emp in employees_query if emp.id == employee_id]
        if branch_id:
            employees_query = [emp for emp in employees_query if emp.branch_id == branch_id]
        if department_id:
            employees_query = [emp for emp in employees_query if emp.department_id == department_id]
        if shift_id:
            employees_query = [emp for emp in employees_query if getattr(emp, 'shift_id', None) == shift_id]

        if not employees_query:
            return jsonify({
                'status': 'warning',
                'message': 'لا يوجد موظفين يطابقون المعايير المحددة',
                'data': {
                    'employees': [],
                    'summary': {}
                }
            }), 200

        # جلب جميع سجلات الحضور في الفترة المحددة
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())
        
        employee_ids = [emp.id for emp in employees_query]
        
        attendances = Attendance.query.filter(
            Attendance.empId.in_(employee_ids),
            Attendance.createdAt >= start_datetime,
            Attendance.createdAt <= end_datetime
        ).order_by(Attendance.createdAt).all()

        # تجميع سجلات الحضور حسب الموظف والتاريخ
        attendance_by_employee = {}
        for attendance in attendances:
            emp_id = attendance.empId
            # إصلاح الخطأ: التحقق من نوع البيانات
            if hasattr(attendance.createdAt, 'date'):
                attendance_date = attendance.createdAt.date()
            else:
                attendance_date = attendance.createdAt
            
            if emp_id not in attendance_by_employee:
                attendance_by_employee[emp_id] = {}
            
            if attendance_date not in attendance_by_employee[emp_id]:
                attendance_by_employee[emp_id][attendance_date] = []
            
            attendance_by_employee[emp_id][attendance_date].append(attendance)

        # إعداد التقرير النهائي
        report_data = []
        overall_summary = {
            'total_employees': len(employees_query),
            'period_from': start_date_str,
            'period_to': end_date_str,
            'total_working_days': total_days,
            'total_present_days': 0,
            'total_absent_days': 0,
            'total_late_days': 0,
            'total_early_leave_days': 0,
            'total_overtime_hours': 0,
            'total_vacation_work_days': 0,
            'employees_summary': []
        }

        # معالجة كل موظف
        for employee in employees_query:
            employee_report = generate_comprehensive_employee_report_updated(
                employee, 
                start_date, 
                end_date, 
                attendance_by_employee.get(employee.id, {})
            )
            
            if employee_report:
                report_data.append(employee_report)
                
                # تحديث الملخص العام
                emp_summary = employee_report['summary']
                overall_summary['total_present_days'] += emp_summary['actual_working_days']
                overall_summary['total_absent_days'] += emp_summary['absent_days']
                overall_summary['total_late_days'] += emp_summary['late_days']
                overall_summary['total_early_leave_days'] += emp_summary['early_leave_days']
                overall_summary['total_overtime_hours'] += emp_summary['total_overtime_hours']
                overall_summary['total_vacation_work_days'] += emp_summary['vacation_work_days']
                
                overall_summary['employees_summary'].append({
                    'employee_id': employee.id,
                    'employee_name': employee.full_name,
                    'department_name': emp_summary['department_name'],
                    'attendance_percentage': emp_summary['attendance_percentage'],
                    'punctuality_percentage': emp_summary['punctuality_percentage']
                })

        return jsonify({
            'status': 'success',
            'message': f'تم إنشاء تقرير الحضور الشهري لـ {len(report_data)} موظف',
            'data': {
                'employees': report_data,
                'summary': overall_summary,
                'generated_at': datetime.now().isoformat(),
                'report_period': f'{start_date_str} إلى {end_date_str}'
            }
        }), 200

    except Exception as e:
        print(f"خطأ في إنشاء تقرير الحضور الشهري: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'حدث خطأ أثناء إنشاء التقرير: {str(e)}'
        }), 500


def generate_comprehensive_employee_report_updated(employee, start_date, end_date, employee_attendances):
    """إنشاء تقرير مفصل وشامل لموظف واحد مع النظام المحدث ودعم العطل"""
    try:
        # جلب بيانات الوردية
        shift = None
        if employee.work_system == 'shift' and employee.shift_id:
            shift = Shift.query.get(employee.shift_id)

        # حساب عدد الأيام في الفترة
        current_date = start_date
        daily_records = []
        
        # إحصائيات مفصلة للموظف
        actual_working_days = 0
        absent_days = 0
        late_days = 0
        early_leave_days = 0
        vacation_work_days = 0
        holiday_work_days = 0  # أيام العمل في العطل الرسمية
        holiday_days = 0  # أيام العطل الرسمية
        
        total_work_hours_inside_shift = 0
        total_overtime_hours = 0
        total_late_hours = 0
        total_early_leave_hours = 0
        total_actual_work_hours = 0
        total_required_work_hours = 0

        # معالجة كل يوم في الفترة
        while current_date <= end_date:
            day_attendances = employee_attendances.get(current_date, [])
            
            # تحديد ما إذا كان اليوم يوم إجازة للموظف باستخدام النظام المحدث
            is_vacation_day, holiday_info = is_employee_vacation_day_updated(employee, current_date, shift)
            
            if day_attendances:
                # الموظف سجل حضور
                daily_record = process_comprehensive_daily_attendance_updated(
                    employee, current_date, day_attendances, shift, is_vacation_day, holiday_info
                )
                
                if holiday_info:
                    # عمل في يوم عطلة رسمية
                    holiday_work_days += 1
                elif is_vacation_day:
                    # عمل في يوم إجازة عادية
                    vacation_work_days += 1
                else:
                    # يوم عمل عادي
                    actual_working_days += 1
                
                # تجميع الإحصائيات (لا نحسب التأخير في العطل الرسمية)
                if daily_record['is_late'] and not holiday_info:
                    late_days += 1
                    total_late_hours += daily_record['late_hours']
                    
                if daily_record['is_early_leave'] and not holiday_info:
                    early_leave_days += 1
                    total_early_leave_hours += daily_record['early_leave_hours']
                
                total_work_hours_inside_shift += daily_record['work_hours_inside_shift']
                total_overtime_hours += daily_record['overtime_hours']
                total_actual_work_hours += daily_record['total_actual_work_hours']
                total_required_work_hours += daily_record['required_work_hours']
                
            else:
                # الموظف غائب - لا نضيف ساعات العمل المطلوبة للغائبين
                daily_record = create_absent_day_record_updated(current_date, shift, is_vacation_day, holiday_info)
                
                if holiday_info:
                    # يوم عطلة رسمية غائب فيه
                    holiday_days += 1
                elif not is_vacation_day:
                    # غياب في يوم عمل عادي - لا نضيف ساعات مطلوبة
                    absent_days += 1
                    # تم إزالة إضافة الساعات المطلوبة للغائبين
                    # total_required_work_hours += 0  # لا نضيف ساعات للغائبين
            
            daily_records.append(daily_record)
            current_date += timedelta(days=1)

        # حساب النسب المئوية والصافي
        total_days = len(daily_records)
        working_days_count = actual_working_days + absent_days  # لا نحسب العطل الرسمية
        
        attendance_percentage = round((actual_working_days / working_days_count) * 100, 2) if working_days_count > 0 else 0
        punctuality_percentage = round(((actual_working_days - late_days) / working_days_count) * 100, 2) if working_days_count > 0 else 0
        
        # حساب صافي الإضافي والتأخير
        net_overtime = max(0, total_overtime_hours - total_late_hours)
        net_late = max(0, total_late_hours - total_overtime_hours)

        # إعداد ملخص الموظف الشامل
        employee_summary = {
            'employee_id': employee.id,
            'employee_name': employee.full_name,
            'fingerprint_id': employee.fingerprint_id,
            'work_system': employee.work_system,
            'position': employee.position,
            'department_name': employee.department.name if employee.department else 'غير محدد',
            'branch_name': employee.branch.name if employee.branch else 'غير محدد',
            'shift_name': shift.name if shift else 'لا توجد وردية',
            'daily_records': daily_records,
            'summary': {
                'total_days_in_period': total_days,
                'actual_working_days': actual_working_days,
                'absent_days': absent_days,
                'vacation_work_days': vacation_work_days,
                'holiday_work_days': holiday_work_days,  # العمل في العطل الرسمية
                'holiday_days': holiday_days,  # العطل الرسمية
                'late_days': late_days,
                'early_leave_days': early_leave_days,
                'attendance_percentage': attendance_percentage,
                'punctuality_percentage': punctuality_percentage,
                
                'total_late_hours': round(total_late_hours, 2),
                'total_early_leave_hours': round(total_early_leave_hours, 2),
                'total_overtime_hours': round(total_overtime_hours, 2),
                'work_hours_inside_shift': round(total_work_hours_inside_shift, 2),
                'total_actual_work_hours': round(total_actual_work_hours, 2),
                'required_work_hours': round(total_required_work_hours, 2),
                
                'net_overtime': round(net_overtime, 2),
                'net_late': round(net_late, 2),
                
                'average_daily_hours': round(total_actual_work_hours / (actual_working_days + vacation_work_days + holiday_work_days), 2) if (actual_working_days + vacation_work_days + holiday_work_days) > 0 else 0,
                'department_name': employee.department.name if employee.department else 'غير محدد'
            }
        }

        return employee_summary

    except Exception as e:
        print(f"خطأ في إنشاء تقرير الموظف {employee.full_name}: {str(e)}")
        return None
        


def process_comprehensive_daily_attendance_updated(employee, date, day_attendances, shift, is_vacation_day, holiday_info=None):
    """معالجة شاملة لحضور يوم واحد للموظف مع النظام المحدث ودعم العطل والإجازات المعتمدة"""
    try:
        # ترتيب سجلات اليوم حسب الوقت
        day_attendances.sort(key=lambda x: x.createdAt)
        
        # الحصول على أول دخول وآخر خروج
        first_check_in = None
        last_check_out = None
        
        for attendance in day_attendances:
            if attendance.checkInTime:
                if not first_check_in:
                    first_check_in = attendance.checkInTime
            if attendance.checkOutTime:
                last_check_out = attendance.checkOutTime

        # الحصول على معلومات الإجازات الساعية المعتمدة لهذا اليوم
        leave_hours, leave_details = get_leave_hours_for_day(employee, date)

        # حساب إجمالي ساعات العمل من الدخول للخروج
        total_actual_work_hours = 0
        if first_check_in and last_check_out:
            start_datetime = datetime.combine(date, first_check_in)
            end_datetime = datetime.combine(date, last_check_out)
            work_duration = end_datetime - start_datetime
            total_actual_work_hours = work_duration.total_seconds() / 3600

        # حساب ساعات العمل الفعلية (مجموع فترات العمل)
        actual_work_periods_hours = 0
        for attendance in day_attendances:
            if attendance.checkInTime and attendance.checkOutTime:
                period_start = datetime.combine(date, attendance.checkInTime)
                period_end = datetime.combine(date, attendance.checkOutTime)
                period_duration = period_end - period_start
                actual_work_periods_hours += period_duration.total_seconds() / 3600

        # متغيرات التحليل
        is_late = False
        is_early_leave = False
        late_hours = 0
        early_leave_hours = 0
        overtime_hours = 0
        work_hours_inside_shift = 0
        required_work_hours = 0
        shift_start_time = None
        shift_end_time = None

        # إذا كان يوم عطلة، لا نحسب التأخير أو الساعات الإضافية
        if is_vacation_day and holiday_info and hasattr(holiday_info, 'name'):
            # في حالة العطل الرسمية، نحتفظ بساعات العمل كما هي لكن بدون خصومات أو مكافآت
            work_hours_inside_shift = actual_work_periods_hours
        elif shift and employee.work_system == 'shift':
            # تحليل بناءً على الوردية المحدثة
            is_working_day, shift_start_time, shift_end_time = get_shift_schedule_for_date(shift, date)
            
            if is_working_day and shift_start_time and shift_end_time:
                required_work_hours = calculate_shift_duration_for_date(shift, date)
                
                # طرح ساعات الإجازة المعتمدة من الساعات المطلوبة
                adjusted_required_hours = max(0, required_work_hours - leave_hours)
                
                # تحليل التأخير (مع مراعاة الإجازات الساعية)
                if first_check_in:
                    expected_start = datetime.combine(date, shift_start_time)
                    actual_start = datetime.combine(date, first_check_in)
                    allowed_delay = timedelta(minutes=shift.allowed_delay_minutes)
                    
                    # التحقق من وجود إجازة ساعية تغطي وقت التأخير
                    is_on_leave, leave_info = is_employee_on_hourly_leave(employee, date, first_check_in)
                    
                    if not is_on_leave and actual_start > expected_start + allowed_delay:
                        is_late = True
                        late_hours = (actual_start - expected_start).total_seconds() / 3600

                # تحليل الخروج المبكر والإضافي
                if last_check_out:
                    expected_end = datetime.combine(date, shift_end_time)
                    actual_end = datetime.combine(date, last_check_out)
                    allowed_early = timedelta(minutes=shift.allowed_exit_minutes)
                    
                    if actual_end < expected_end - allowed_early:
                        # التحقق من وجود إجازة ساعية تغطي وقت الخروج المبكر
                        is_on_leave, leave_info = is_employee_on_hourly_leave(employee, date, last_check_out)
                        
                        if not is_on_leave:
                            is_early_leave = True
                            early_leave_hours = (expected_end - actual_end).total_seconds() / 3600
                    elif actual_end > expected_end:
                        overtime_hours = (actual_end - expected_end).total_seconds() / 3600

                # حساب ساعات العمل داخل الوردية (مع مراعاة الإجازات)
                if first_check_in and last_check_out:
                    shift_start_dt = datetime.combine(date, shift_start_time)
                    shift_end_dt = datetime.combine(date, shift_end_time)
                    actual_start_dt = datetime.combine(date, first_check_in)
                    actual_end_dt = datetime.combine(date, last_check_out)
                    
                    effective_start = max(actual_start_dt, shift_start_dt)
                    effective_end = min(actual_end_dt, shift_end_dt)
                    
                    if effective_end > effective_start:
                        work_hours_inside_shift = (effective_end - effective_start).total_seconds() / 3600
                        # إضافة ساعات الإجازة المعتمدة للعمل داخل الوردية
                        work_hours_inside_shift += leave_hours
        else:
            # في حالة عدم وجود وردية أو نظام ساعات
            work_hours_inside_shift = actual_work_periods_hours + leave_hours
            required_work_hours = 8

        # تجهيز فترات الحضور
        attendance_periods = []
        for attendance in day_attendances:
            attendance_periods.append({
                'check_in': str(attendance.checkInTime) if attendance.checkInTime else None,
                'check_out': str(attendance.checkOutTime) if attendance.checkOutTime else None,
                'check_in_reason': attendance.checkInReason,
                'check_out_reason': attendance.checkOutReason
            })

        # تحديد الحالة
        status = 'حاضر'
        if is_vacation_day:
            if holiday_info and hasattr(holiday_info, 'name'):
                status = f'حاضر (عطلة رسمية - {holiday_info.name})'
            elif holiday_info and hasattr(holiday_info, 'leave_type'):
                if holiday_info.leave_type == 'daily_leave':
                    status = 'حاضر (إجازة يومية معتمدة)'
                else:
                    status = 'حاضر (يوم إجازة)'
            else:
                status = 'حاضر (يوم إجازة)'
        elif is_late:
            status = 'متأخر'
        
        if not last_check_out:
            status += ' (لم يسجل خروج)'

        # إعداد معلومات الإجازة المعتمدة
        leave_info = None
        if holiday_info and hasattr(holiday_info, 'leave_type'):
            leave_info = {
                'id': holiday_info.id,
                'leave_type': holiday_info.leave_type,
                'transaction_id': holiday_info.transaction_id,
                'reason': holiday_info.reason,
                'notes': holiday_info.notes
            }

        return {
            'date': date.isoformat(),
            'day_name': get_arabic_day_name(date),
            'status': status,
            'is_vacation_day': is_vacation_day,
            'is_holiday': holiday_info is not None and hasattr(holiday_info, 'name'),
            'is_on_approved_leave': holiday_info is not None and hasattr(holiday_info, 'leave_type'),
            'holiday_info': {
                'name': holiday_info.name,
                'type': holiday_info.holiday_type,
                'is_paid': holiday_info.is_paid,
                'description': holiday_info.description
            } if holiday_info and hasattr(holiday_info, 'name') else None,
            'leave_info': leave_info,
            'approved_leave_hours': leave_hours,
            'leave_details': leave_details,
            
            # أوقات الحضور والانصراف المحدثة
            'required_check_in': str(shift_start_time) if shift_start_time else None,
            'required_check_out': str(shift_end_time) if shift_end_time else None,
            'actual_check_in': str(first_check_in) if first_check_in else None,
            'actual_check_out': str(last_check_out) if last_check_out else None,
            
            # ساعات العمل (مع مراعاة الإجازات المعتمدة)
            'total_actual_work_hours': round(total_actual_work_hours, 2),
            'work_hours_inside_shift': round(work_hours_inside_shift, 2),
            'required_work_hours': round(required_work_hours, 2) if not is_vacation_day else 0,
            'overtime_hours': round(overtime_hours, 2) if not (is_vacation_day and holiday_info and hasattr(holiday_info, 'name')) else 0,
            
            # التأخير والخروج المبكر (لا يطبق في العطل الرسمية أو الإجازات المعتمدة)
            'is_late': is_late and not (is_vacation_day and holiday_info),
            'is_early_leave': is_early_leave and not (is_vacation_day and holiday_info),
            'late_hours': round(late_hours, 2) if not (is_vacation_day and holiday_info) else 0,
            'early_leave_hours': round(early_leave_hours, 2) if not (is_vacation_day and holiday_info) else 0,
            
            'attendance_periods': attendance_periods,
            'shift_name': shift.name if shift else 'لا توجد وردية',
            'notes': f"فترات الحضور: {len(attendance_periods)}" + 
                    (f" - عطلة رسمية: {holiday_info.name}" if holiday_info and hasattr(holiday_info, 'name') else 
                     f" - إجازة معتمدة: {holiday_info.leave_type}" if holiday_info and hasattr(holiday_info, 'leave_type') else
                     " - يوم إجازة" if is_vacation_day else "") +
                    (f" - ساعات إجازة معتمدة: {leave_hours}" if leave_hours > 0 else "")
        }
    
    except Exception as e:
        print(f"خطأ في معالجة حضور اليوم {date}: {str(e)}")
        return create_absent_day_record_updated(date, shift, is_vacation_day, holiday_info)


def create_absent_day_record_updated(date, shift, is_vacation_day, holiday_info=None):
    """إنشاء سجل لليوم الغائب مع النظام المحدث ودعم العطل - الساعات المطلوبة = 0 للغائبين"""
    status = 'غائب'
    notes = 'لم يسجل حضور'
    
    if is_vacation_day:
        if holiday_info:
            # يوم عطلة رسمية
            status = f'عطلة رسمية ({holiday_info.name})'
            notes = f'عطلة رسمية: {holiday_info.name}'
            if holiday_info.description:
                notes += f' - {holiday_info.description}'
        else:
            # إجازة أسبوعية أو حسب الوردية
            status = 'إجازة أسبوعية'
            notes = 'إجازة أسبوعية حسب الوردية'
    
    # الحصول على أوقات الوردية للتاريخ المحدد
    shift_start_time = None
    shift_end_time = None
    # تم تعديل هذا الجزء: الساعات المطلوبة = 0 للغائبين
    required_work_hours = 0  # دائماً 0 للغائبين بغض النظر عن اليوم
    
    if shift and not is_vacation_day:
        is_working_day, shift_start_time, shift_end_time = get_shift_schedule_for_date(shift, date)
        # حتى لو كان يوم عمل، الساعات المطلوبة = 0 للغائبين
        # required_work_hours = 0  # تبقى 0
    
    return {
        'date': date.isoformat(),
        'day_name': get_arabic_day_name(date),
        'status': status,
        'is_vacation_day': is_vacation_day,
        'is_holiday': holiday_info is not None,
        'holiday_info': {
            'name': holiday_info.name,
            'type': holiday_info.holiday_type,
            'is_paid': holiday_info.is_paid,
            'description': holiday_info.description
        } if holiday_info else None,
        
        # أوقات مطلوبة محدثة
        'required_check_in': str(shift_start_time) if shift_start_time else None,
        'required_check_out': str(shift_end_time) if shift_end_time else None,
        'actual_check_in': None,
        'actual_check_out': None,
        
        # ساعات صفر
        'total_actual_work_hours': 0,
        'work_hours_inside_shift': 0,
        'required_work_hours': 0,  # دائماً 0 للغائبين
        'overtime_hours': 0,
        
        # لا يوجد تأخير أو خروج مبكر في العطل
        'is_late': False,
        'is_early_leave': False,
        'late_hours': 0,
        'early_leave_hours': 0,
        
        'attendance_periods': [],
        'shift_name': shift.name if shift else 'لا توجد وردية',
        'notes': notes
    }


def is_employee_vacation_day(employee, date, shift):
    """
    تحديد ما إذا كان اليوم يوم إجازة للموظف
    يمكن تطوير هذه الدالة حسب نظام الإجازات في الشركة
    """
    # مثال: الجمعة والسبت إجازة أسبوعية
    weekday = date.weekday()
    
    # إذا كان الموظف له وردية، تحقق من أيام عمل الوردية
    if shift:
        # يمكن إضافة حقل working_days في جدول Shift
        # افتراضياً: الجمعة (4) والسبت (5) إجازة
        if weekday in [4, 5]:  # الجمعة والسبت
            return True
    
    # يمكن إضافة فحص للإجازات الرسمية من جدول منفصل
    # مثال: جدول public_holidays
    
    return False




def get_arabic_day_name(date):
    """الحصول على اسم اليوم باللغة العربية"""
    arabic_days = {
        0: 'الاثنين',
        1: 'الثلاثاء', 
        2: 'الأربعاء',
        3: 'الخميس',
        4: 'الجمعة',
        5: 'السبت',
        6: 'الأحد'
    }
    return arabic_days.get(date.weekday(), 'غير محدد')


def is_employee_on_leave_updated(employee, target_date, shift):
    """
    تحديد ما إذا كان الموظف في إجازة في التاريخ المحدد
    يدعم الإجازات المعتمدة من نظام المعاملات
    """
    # أولاً: التحقق من العطل الرسمية
    holiday = Holiday.is_holiday(
        target_date, 
        employee.branch_id if hasattr(employee, 'branch_id') else None,
        employee.department_id if hasattr(employee, 'department_id') else None
    )
    
    if holiday:
        return True, holiday, 'holiday'  # إرجاع نوع الإجازة أيضاً
    
    # ثانياً: التحقق من الإجازات المعتمدة
    from app.models.leave import Leave
    leaves = Leave.get_employee_leaves_for_date(employee.id, target_date)
    
    for leave in leaves:
        if leave.is_date_covered_by_leave(target_date):
            return True, leave, 'approved_leave'
    
    # ثالثاً: التحقق من جدول الوردية إذا وجد
    if not shift:
        # إذا لم تكن هناك وردية، اعتبر الجمعة والسبت إجازة
        weekday = target_date.weekday()
        is_weekend = weekday in [4, 5]  # الجمعة والسبت
        return is_weekend, None, 'weekend'
    
    # تحقق من جدول الوردية الجديد
    is_working_day, _, _ = get_shift_schedule_for_date(shift, target_date)
    return not is_working_day, None, 'shift_off'

def is_employee_on_hourly_leave(employee, target_date, check_time):
    """
    فحص ما إذا كان الموظف في إجازة ساعية في الوقت المحدد
    """
    from app.models.leave import Leave
    leaves = Leave.get_employee_leaves_for_date(employee.id, target_date)
    
    for leave in leaves:
        if leave.leave_type == 'hourly_leave' and leave.is_time_covered_by_leave(target_date, check_time):
            return True, leave
    
    return False, None

def get_leave_hours_for_day(employee, target_date):
    """
    الحصول على عدد ساعات الإجازة المعتمدة للموظف في يوم محدد
    """
    from app.models.leave import Leave
    leaves = Leave.get_employee_leaves_for_date(employee.id, target_date)
    
    total_leave_hours = 0
    leave_details = []
    
    for leave in leaves:
        if leave.leave_type == 'hourly_leave' and leave.is_date_covered_by_leave(target_date):
            total_leave_hours += leave.hours or 0
            leave_details.append({
                'id': leave.id,
                'hours': leave.hours,
                'start_time': str(leave.start_time) if leave.start_time else None,
                'end_time': str(leave.end_time) if leave.end_time else None,
                'reason': leave.reason,
                'transaction_id': leave.transaction_id
            })
    
    return total_leave_hours, leave_details



# =======================
# Helper Functions المحدثة
# =======================

def get_day_name_english(date):
    """تحويل التاريخ إلى اسم اليوم بالإنجليزية"""
    days = {
        0: 'monday',    # الاثنين
        1: 'tuesday',   # الثلاثاء
        2: 'wednesday', # الأربعاء
        3: 'thursday',  # الخميس
        4: 'friday',    # الجمعة
        5: 'saturday',  # السبت
        6: 'sunday'     # الأحد
    }
    return days.get(date.weekday())

def get_shift_schedule_for_date(shift, target_date):
    """
    الحصول على جدول الوردية لتاريخ محدد
    يرجع: (is_working_day, start_time, end_time)
    """
    if not shift or not shift.daily_schedule:
        return False, None, None
    
    day_name = get_day_name_english(target_date)
    day_schedule = shift.daily_schedule.get(day_name, {})
    
    if not day_schedule.get('is_active', False):
        return False, None, None
    
    try:
        start_time = time.fromisoformat(day_schedule.get('start_time', ''))
        end_time = time.fromisoformat(day_schedule.get('end_time', ''))
        return True, start_time, end_time
    except (ValueError, TypeError):
        return False, None, None

def calculate_shift_duration_for_date(shift, target_date):
    """حساب مدة الوردية لتاريخ محدد"""
    is_working_day, start_time, end_time = get_shift_schedule_for_date(shift, target_date)
    
    if not is_working_day or not start_time or not end_time:
        return 0
    
    start_seconds = start_time.hour * 3600 + start_time.minute * 60
    end_seconds = end_time.hour * 3600 + end_time.minute * 60
    
    # التعامل مع الورديات التي تمتد لليوم التالي
    if end_seconds < start_seconds:
        end_seconds += 24 * 3600
    
    duration_seconds = end_seconds - start_seconds
    return duration_seconds / 3600

def is_employee_vacation_day_updated(employee, date, shift):
    """تحديد ما إذا كان اليوم يوم إجازة للموظف مع دعم نظام العطل والإجازات المعتمدة"""
    
    # أولاً: التحقق من العطل الرسمية
    holiday = Holiday.is_holiday(
        date, 
        employee.branch_id if hasattr(employee, 'branch_id') else None,
        employee.department_id if hasattr(employee, 'department_id') else None
    )
    
    if holiday:
        return True, holiday  # إرجاع معلومات العطلة الرسمية
    
    # ثانياً: التحقق من الإجازات المعتمدة
    from app.models.leave import Leave
    leaves = Leave.get_employee_leaves_for_date(employee.id, date)
    
    for leave in leaves:
        if leave.is_date_covered_by_leave(date):
            # إذا كانت إجازة يومية، اعتبر اليوم كله إجازة
            if leave.leave_type == 'daily_leave':
                return True, leave
            # إذا كانت إجازة ساعية، لا نعتبر اليوم كله إجازة
            # ولكن نتعامل معها في معالجة الحضور
    
    # ثالثاً: التحقق من جدول الوردية إذا وجد
    if not shift:
        # إذا لم تكن هناك وردية، اعتبر الجمعة والسبت إجازة
        weekday = date.weekday()
        is_weekend = weekday in [4, 5]  # الجمعة والسبت
        return is_weekend, None
    
    # تحقق من جدول الوردية الجديد
    is_working_day, _, _ = get_shift_schedule_for_date(shift, date)
    return not is_working_day, None
    


# =======================
# Updated Functions
# =======================

def process_shift_attendance_updated(employee, employee_attendances, target_date):
    """معالجة حضور الموظف في نظام الورديات المحدث"""
    shift = Shift.query.filter_by(id=employee.shift_id).first()
    if not shift:
        return None

    # الحصول على جدول الوردية لهذا التاريخ
    is_working_day, shift_start_time, shift_end_time = get_shift_schedule_for_date(shift, target_date)
    
    if not is_working_day:
        # إذا لم يكن يوم عمل حسب الوردية، اعتبره يوم إجازة
        return None

    first_check_in = min(att.checkInTime for att in employee_attendances if att.checkInTime)
    last_check_out = max(
        (att.checkOutTime for att in employee_attendances if att.checkOutTime),
        default=None
    )

    # حساب أوقات الحضور والانصراف الفعلية مع مراعاة التأخير المسموح به
    allowed_delay = timedelta(minutes=shift.allowed_delay_minutes)
    allowed_exit = timedelta(minutes=shift.allowed_exit_minutes)

    shift_start_seconds = time_to_seconds(shift_start_time)
    shift_end_seconds = time_to_seconds(shift_end_time)
    first_check_in_seconds = time_to_seconds(first_check_in)
    last_check_out_seconds = time_to_seconds(last_check_out) if last_check_out else None

    # حساب حالة الحضور
    if first_check_in_seconds <= shift_start_seconds + allowed_delay.total_seconds():
        actual_check_in_time = shift_start_time
        check_in_status = "On Time"
    else:
        actual_check_in_time = first_check_in
        check_in_status = "Late"

    # حساب حالة الانصراف
    if last_check_out:
        if last_check_out_seconds >= shift_end_seconds - allowed_exit.total_seconds():
            actual_check_out_time = shift_end_time
            check_out_status = "On Time"
        else:
            actual_check_out_time = last_check_out
            check_out_status = "Early"
    else:
        actual_check_out_time = None
        check_out_status = "No Check-out"

    # حساب إجمالي وقت العمل والاستراحة
    total_work_time, total_break_time = calculate_work_and_break_time(employee_attendances)

    return format_attendance_summary_updated(
        employee, target_date, actual_check_in_time, check_in_status,
        actual_check_out_time, check_out_status, total_work_time,
        total_break_time, employee_attendances, shift_start_time, shift_end_time
    )

def format_attendance_summary_updated(employee, date_str, check_in_time, check_in_status,
                                    check_out_time, check_out_status, total_work_time,
                                    total_break_time, employee_attendances, 
                                    required_start_time, required_end_time):
    """تنسيق ملخص الحضور مع كامل بيانات الموظف المحدث"""
    
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
        'checkOutTime': str(att.checkOutTime) if att.checkOutTime else None,
        'checkInReason': att.checkInReason,
        'checkOutReason': att.checkOutReason,
        'attendanceId': att.id
    } for att in employee_attendances]

    # الحصول على الأوقات الفعلية للدخول والخروج (بدون قص)
    first_actual_check_in = min(att.checkInTime for att in employee_attendances if att.checkInTime)
    last_actual_check_out = max(
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

    # تجميع النتيجة النهائية
    return {
        'employee': employee_data,
        'date': date_str,
        'requiredCheckIn': str(required_start_time) if required_start_time else None,  # الوقت المطلوب المحدث
        'requiredCheckOut': str(required_end_time) if required_end_time else None,    # الوقت المطلوب المحدث
        'actualCheckIn': str(check_in_time),
        'checkInStatus': check_in_status,
        'actualCheckOut': str(check_out_time) if check_out_time else None,
        'checkOutStatus': check_out_status,
        'totalWorkTime': f"{total_work_hours} hours {total_work_minutes} minutes",
        'totalBreakTime': f"{total_break_hours} hours {total_break_minutes} minutes",
        'nextAction': next_action,
        'attendancePeriods': attendance_periods,
        'firstCheckIn': str(first_actual_check_in),  # الوقت الفعلي للدخول الأول
        'lastCheckOut': str(last_actual_check_out) if last_actual_check_out else None  # الوقت الفعلي للخروج الأخير
    }