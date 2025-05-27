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

    # إنشاء تسجيل حضور جديد مع الوقت المخصص وسبب الدخول
    attendance = Attendance(
        empId=data['empId'],
        checkInTime=check_in_time,
        createdAt=datetime.now(),
        checkInReason=data.get('checkInReason')  # إضافة سبب الدخول إذا وجد
    )

    db.session.add(attendance)
    db.session.commit()

    # الحصول على بيانات الموظف لإرجاعها في الاستجابة
    employee_data = {
        'id': employee.id,
        'name': employee.full_name,
        'work_system': employee.work_system
    }

    return jsonify({
        'message': 'Check-in successful',
        'attendance': {
            'id': attendance.id,
            'employee': employee_data,
            'createdAt': str(attendance.createdAt),
            'checkInTime': str(attendance.checkInTime),
            'actualCheckIn': str(attendance.checkInTime),
            'checkInReason': attendance.checkInReason
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

# دالة لمزامنة سجلات البصمة بشكل جماعي مع أخذ أول وآخر بصمة فقط
def sync_fingerprint_records():
    """
    مزامنة سجلات البصمة الجماعية مع أخذ أول وآخر بصمة لكل موظف في كل يوم
    مع حذف السجلات السابقة لكل يوم تتم مزامنته فقط
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
            'failed': 0,
            'duplicates_removed': 0,
            'employees_processed': 0,
            'days_processed': 0,
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
                        # إذا كان timestamp كائن datetime بالفعل
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
        
        # المرحلة 2: معالجة البصمات لكل موظف ولكل يوم وإنشاء سجلات الدخول والخروج
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
                    
                    # حذف سجلات هذا الموظف لهذا اليوم فقط قبل إضافة سجلات جديدة
                    existing_records = Attendance.query.filter(
                        Attendance.empId == emp_id,
                        cast(Attendance.createdAt, Date) == record_date
                    ).all()
                    
                    deleted_count = 0
                    if existing_records:
                        for old_record in existing_records:
                            db.session.delete(old_record)
                            deleted_count += 1
                        
                        results['duplicates_removed'] += deleted_count
                        print(f"تم حذف {deleted_count} سجل قديم للموظف {employee_name} في {date_key}")
                    
                    # استخراج أول وآخر بصمة
                    first_timestamp = timestamps[0]
                    last_timestamp = timestamps[-1] if len(timestamps) > 1 else None
                    
                    # التحقق من أن الفرق الزمني منطقي (أكثر من 5 دقائق)
                    check_out_time = None
                    check_out_datetime = None
                    
                    if last_timestamp and len(timestamps) > 1:
                        time_diff = (last_timestamp['time'] - first_timestamp['time']).total_seconds()
                        if time_diff > 300:  # أكثر من 5 دقائق
                            check_out_time = last_timestamp['time'].time()
                            check_out_datetime = last_timestamp['time']
                        else:
                            print(f"تجاهل وقت الخروج للموظف {employee_name} - فرق زمني قصير: {time_diff} ثانية")
                    
                    # إنشاء سجل حضور جديد
                    attendance = Attendance(
                        empId=employee.id,
                        checkInTime=first_timestamp['time'].time(),
                        createdAt=first_timestamp['time'],
                        checkInReason=f'Fingerprint sync - first of {len(timestamps)} records',
                        checkOutTime=check_out_time,
                        checkOutReason=f'Fingerprint sync - last of {len(timestamps)} records' if check_out_time else None
                    )
                    
                    # إضافة السجل إلى قاعدة البيانات
                    db.session.add(attendance)
                    results['success'] += 1
                    
                    # إضافة تفاصيل العملية
                    processing_info = {
                        'employee_id': employee.id,
                        'employee_name': employee.full_name,
                        'fingerprint_id': fingerprint_id,
                        'date': date_key,
                        'status': 'success',
                        'total_fingerprints': len(timestamps),
                        'deleted_old_records': deleted_count,
                        'check_in_time': first_timestamp['time'].strftime("%H:%M:%S"),
                        'check_out_time': check_out_time.strftime("%H:%M:%S") if check_out_time else None,
                        'all_timestamps': [ts['time'].strftime("%H:%M:%S") for ts in timestamps]
                    }
                    
                    results['processing_summary'].append(processing_info)
                    print(f"✓ تم إنشاء سجل حضور للموظف {employee_name}: دخول {processing_info['check_in_time']}, خروج {processing_info['check_out_time'] or 'غير محدد'}")
                    
                except Exception as e:
                    error_msg = f"خطأ في معالجة الموظف {employee_name or emp_id} في التاريخ {date_key}: {str(e)}"
                    print(error_msg)
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
        success_message = f'تمت مزامنة سجلات الحضور بنجاح: '
        success_message += f'{results["success"]} سجل تم إنشاؤه، '
        success_message += f'{results["failed"]} فشل، '
        success_message += f'{results["duplicates_removed"]} سجل قديم تم استبداله، '
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
    branch_id = request.args.get('branch_id', type=int)
    department_id = request.args.get('department_id', type=int)
    shift_id = request.args.get('shift_id', type=int)

    if not date_str:
        return jsonify({'message': 'Date parameter is required'}), 400

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d')
        start_datetime = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_datetime = start_datetime + timedelta(days=1)

        # جلب جميع الموظفين
        all_employees = Employee.query.all()

        # جلب جميع الحضور في هذا اليوم (نستخدمه لحساب بصمات الدخول/الخروج لكل موظف)
        attendances = Attendance.query.filter(
            Attendance.createdAt >= start_datetime,
            Attendance.createdAt < end_datetime
        ).all()

        result = []

        for employee in all_employees:
            # تطبيق الفلاتر (الفرع، القسم، الوردية)
            if branch_id and employee.branch_id != branch_id:
                continue
            if department_id and employee.department_id != department_id:
                continue
            if shift_id and employee.shift_id != shift_id:
                continue

            # فلترة تسجيلات الحضور الخاصة بهذا الموظف فقط
            emp_attendances_today = [att for att in attendances if att.empId == employee.id]

            # عدد تسجيلات الدخول والخروج
            total_checkin = sum(1 for att in emp_attendances_today if att.checkInTime)
            total_checkout = sum(1 for att in emp_attendances_today if att.checkOutTime)

            # الشرط: لا وجود لتسجيل دخول، أو دخول واحد فقط بدون خروج
            if (total_checkin == 0) or (total_checkin == 1 and total_checkout == 0):

                # معالجة الحضور حسب نظام العمل
                if employee.work_system == 'shift':
                    attendance_summary = process_shift_attendance(employee, emp_attendances_today, date_str)
                else:
                    attendance_summary = process_hours_attendance(employee, emp_attendances_today, date_str)

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
    return t.hour * 3600 + t.minute * 60 + t.second