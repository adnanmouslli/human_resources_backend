from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from sqlalchemy import func, cast, Date
from app import db
from app.models import MonthlyAttendance, Employee
from app.models.attendance_type import AttendanceType
from app.utils import token_required
import json

monthly_attendance_bp = Blueprint('monthly_attendance', __name__)

# إنشاء سجل دوام جديد
@monthly_attendance_bp.route('/api/monthly-attendance', methods=['POST'])
@token_required
def create_monthly_attendance(user_id):
    try:
        data = request.get_json()

        # التحقق من الحقول المطلوبة
        required_fields = ['employee_id', 'attendance_type']
        if not all(field in data for field in required_fields):
            return jsonify({'message': 'Missing required fields'}), 400

        # التحقق من وجود الموظف
        employee = Employee.query.get(data['employee_id'])
        if not employee:
            return jsonify({'message': 'Employee not found'}), 404

        # التحقق من عدم وجود سجل لنفس اليوم
        existing_record = MonthlyAttendance.query.filter(
            MonthlyAttendance.employee_id == data['employee_id'],
            cast(MonthlyAttendance.date, Date) == datetime.now().date()
        ).first()

        if existing_record:
            return jsonify({'message': 'Attendance record already exists for today'}), 409


        attendance = MonthlyAttendance(
            employee_id=data['employee_id'],
            attendance_type=data['attendance_type'],
            is_excused_absence=data.get('is_excused_absence', False),
            excuse_document=data.get('excuse_document'),
            check_in=datetime.now().time() if data['attendance_type'].lower() != 'absent' else None,
            notes=data.get('notes')
        )


        db.session.add(attendance)
        db.session.commit()

        return jsonify({
            'message': 'Attendance record created successfully',
            'attendance': {
                'id': attendance.id,
                'employee_id': attendance.employee_id,
                'date': attendance.date.isoformat(),
                'attendance_type': attendance.attendance_type.value,
                'check_in': str(attendance.check_in) if attendance.check_in else None,
                'check_out': str(attendance.check_out) if attendance.check_out else None,
                'is_excused_absence': attendance.is_excused_absence,
                'notes': attendance.notes
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Error creating attendance record: {str(e)}'}), 500

# تسجيل وقت الانصراف
@monthly_attendance_bp.route('/api/monthly-attendance/checkout/<int:id>', methods=['PUT'])
@token_required
def checkout(user_id, id):
    try:
        attendance = MonthlyAttendance.query.get(id)
        if not attendance:
            return jsonify({'message': 'Attendance record not found'}), 404

        if attendance.check_out:
            return jsonify({'message': 'Checkout already recorded'}), 400

        attendance.check_out = datetime.now().time()
        db.session.commit()

        return jsonify({
            'message': 'Checkout recorded successfully',
            'attendance': {
                'id': attendance.id,
                'employee_id': attendance.employee_id,
                'date': attendance.date.isoformat(),
                'attendance_type': attendance.attendance_type.value,
                'check_in': str(attendance.check_in),
                'check_out': str(attendance.check_out)
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Error recording checkout: {str(e)}'}), 500

# الحصول على سجلات دوام موظف معين
@monthly_attendance_bp.route('/api/monthly-attendance/employee/<int:employee_id>', methods=['GET'])
@token_required
def get_employee_attendance(user_id, employee_id):
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        query = MonthlyAttendance.query.filter_by(employee_id=employee_id)

        if start_date and end_date:
            query = query.filter(
                MonthlyAttendance.date >= datetime.strptime(start_date, '%Y-%m-%d'),
                MonthlyAttendance.date <= datetime.strptime(end_date, '%Y-%m-%d')
            )

        records = query.order_by(MonthlyAttendance.date.desc()).all()

        return jsonify([{
            'id': record.id,
            'date': record.date.isoformat(),
            'attendance_type': record.attendance_type.value,
            'check_in': str(record.check_in) if record.check_in else None,
            'check_out': str(record.check_out) if record.check_out else None,
            'is_excused_absence': record.is_excused_absence,
            'notes': record.notes
        } for record in records]), 200

    except Exception as e:
        return jsonify({'message': f'Error fetching attendance records: {str(e)}'}), 500

# الحصول على تقرير شهري
@monthly_attendance_bp.route('/api/monthly-attendance/report', methods=['GET'])
@token_required
def get_monthly_report(user_id):
    try:
        year = request.args.get('year', datetime.now().year)
        month = request.args.get('month', datetime.now().month)
        employee_id = request.args.get('employee_id')

        start_date = datetime(int(year), int(month), 1)
        if int(month) == 12:
            end_date = datetime(int(year) + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(int(year), int(month) + 1, 1) - timedelta(days=1)

        query = MonthlyAttendance.query.filter(
            MonthlyAttendance.date >= start_date,
            MonthlyAttendance.date <= end_date
        )

        if employee_id:
            query = query.filter_by(employee_id=employee_id)

        records = query.order_by(
            MonthlyAttendance.employee_id,
            MonthlyAttendance.date
        ).all()

        # تجميع البيانات حسب الموظف
        report = {}
        for record in records:
            emp_id = record.employee_id
            if emp_id not in report:
                report[emp_id] = {
                    'employee': {
                        'id': record.employee.id,
                        'name': record.employee.full_name
                    },
                    'attendance_summary': {
                        'full_days': 0,
                        'half_days': 0,
                        'online_days': 0,
                        'excused_absences': 0,
                        'unexcused_absences': 0
                    },
                    'daily_records': []
                }

            # تحديث الإحصائيات
            if record.is_excused_absence:
                report[emp_id]['attendance_summary']['excused_absences'] += 1
            else:
                if record.attendance_type == AttendanceType.FULL_DAY:
                    report[emp_id]['attendance_summary']['full_days'] += 1
                elif record.attendance_type == AttendanceType.HALF_DAY:
                    report[emp_id]['attendance_summary']['half_days'] += 1
                elif record.attendance_type == AttendanceType.ONLINE_DAY:
                    report[emp_id]['attendance_summary']['online_days'] += 1

            # إضافة السجل اليومي
            report[emp_id]['daily_records'].append({
                'date': record.date.isoformat(),
                'attendance_type': record.attendance_type.value,
                'check_in': str(record.check_in) if record.check_in else None,
                'check_out': str(record.check_out) if record.check_out else None,
                'is_excused_absence': record.is_excused_absence,
                'notes': record.notes
            })

        return jsonify(list(report.values())), 200

    except Exception as e:
        return jsonify({'message': f'Error generating monthly report: {str(e)}'}), 500

# تحديث سجل دوام
@monthly_attendance_bp.route('/api/monthly-attendance/<int:id>', methods=['PUT'])
@token_required
def update_attendance(user_id, id):
    try:
        attendance = MonthlyAttendance.query.get(id)
        if not attendance:
            return jsonify({'message': 'Attendance record not found'}), 404

        data = request.get_json()
        
        # تحديث الحقول المسموح بها
        if 'attendance_type' in data:
            attendance.attendance_type = data['attendance_type']
        if 'is_excused_absence' in data:
            attendance.is_excused_absence = data['is_excused_absence']
        if 'excuse_document' in data:
            attendance.excuse_document = data['excuse_document']
        if 'notes' in data:
            attendance.notes = data['notes']

        db.session.commit()

        return jsonify({
            'message': 'Attendance record updated successfully',
            'attendance': {
                'id': attendance.id,
                'employee_id': attendance.employee_id,
                'date': attendance.date.isoformat(),
                'attendance_type': attendance.attendance_type.value,
                'check_in': str(attendance.check_in) if attendance.check_in else None,
                'check_out': str(attendance.check_out) if attendance.check_out else None,
                'is_excused_absence': attendance.is_excused_absence,
                'notes': attendance.notes
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Error updating attendance record: {str(e)}'}), 500

# حذف سجل دوام
@monthly_attendance_bp.route('/api/monthly-attendance/<int:id>', methods=['DELETE'])
@token_required
def delete_attendance(user_id, id):
    try:
        attendance = MonthlyAttendance.query.get(id)
        if not attendance:
            return jsonify({'message': 'Attendance record not found'}), 404

        db.session.delete(attendance)
        db.session.commit()

        return jsonify({'message': 'Attendance record deleted successfully'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Error deleting attendance record: {str(e)}'}), 500

# الحصول على إحصائيات الدوام
@monthly_attendance_bp.route('/api/monthly-attendance/stats', methods=['GET'])
@token_required
def get_attendance_stats(user_id):
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        employee_id = request.args.get('employee_id')

        query = MonthlyAttendance.query

        if start_date and end_date:
            query = query.filter(
                MonthlyAttendance.date >= datetime.strptime(start_date, '%Y-%m-%d'),
                MonthlyAttendance.date <= datetime.strptime(end_date, '%Y-%m-%d')
            )

        if employee_id:
            query = query.filter_by(employee_id=employee_id)

        # إحصائيات عامة
        total_records = query.count()
        full_days = query.filter_by(attendance_type=AttendanceType.FULL_DAY).count()
        half_days = query.filter_by(attendance_type=AttendanceType.HALF_DAY).count()
        online_days = query.filter_by(attendance_type=AttendanceType.ONLINE_DAY).count()
        excused_absences = query.filter_by(is_excused_absence=True).count()

        # تجميع البيانات حسب نوع الدوام
        attendance_by_type = {
            'full_days': full_days,
            'half_days': half_days,
            'online_days': online_days,
            'excused_absences': excused_absences
        }

        return jsonify({
            'total_records': total_records,
            'attendance_by_type': attendance_by_type,
            'period': {
                'start_date': start_date,
                'end_date': end_date
            }
        }), 200

    except Exception as e:
        return jsonify({'message': f'Error fetching attendance statistics: {str(e)}'}), 500
    

# إضافة route جديد لسجلات اليوم
@monthly_attendance_bp.route('/api/monthly-attendance/daily', methods=['GET'])
@token_required
def get_daily_attendance(user_id):
    try:
        today = datetime.now().date()
        
        records = MonthlyAttendance.query.filter(
            cast(MonthlyAttendance.date, Date) == today
        ).order_by(MonthlyAttendance.date.desc()).all()

        return jsonify([{
            'id': record.id,
            'employee_id': record.employee_id,
            'employee': {
                'id': record.employee.id,
                'name': record.employee.full_name
            } if record.employee else None,
            'date': record.date.isoformat(),
            'attendance_type': record.attendance_type.value,
            'check_in': str(record.check_in) if record.check_in else None,
            'check_out': str(record.check_out) if record.check_out else None,
            'is_excused_absence': record.is_excused_absence,
            'excuse_document': record.excuse_document,
            'notes': record.notes
        } for record in records]), 200

    except Exception as e:
        return jsonify({'message': f'Error fetching daily attendance: {str(e)}'}), 500