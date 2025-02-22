from flask import Blueprint, request, jsonify
from datetime import datetime
from sqlalchemy import extract
from decimal import Decimal
from app import db
from app.models import AttendanceType, Employee, JobTitle, MonthlyAttendance, Attendance, ProductionMonitoring, Advance, Shift
from app.utils import token_required

payroll_bp = Blueprint('payroll', __name__)
from flask import Blueprint, request, jsonify
from datetime import datetime
from sqlalchemy import extract
from decimal import Decimal
from app import db
from app.models import Employee, JobTitle, MonthlyAttendance, Attendance, ProductionMonitoring, Advance
from app.utils import token_required

payroll_bp = Blueprint('payroll', __name__)
@payroll_bp.route('/api/payroll/calculate', methods=['POST'])
@token_required
def calculate_monthly_payroll(user_id):
    try:
        data = request.get_json()
        required_fields = ['month', 'year']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({'message': f'Missing fields: {", ".join(missing_fields)}'}), 400

        month = int(data['month'])
        year = int(data['year'])

        if not (1 <= month <= 12):
            return jsonify({'message': 'Invalid month value'}), 400

        # جلب جميع الموظفين
        employees = Employee.query.all()
        
        # تهيئة المتغيرات لتجميع النتائج
        monthly_system_employees = []
        production_system_employees = []
        shift_system_employees = []
        hourly_employees = []

        # إحصائيات عامة
        general_statistics = {
            'total_employees': len(employees),
            'total_payroll': Decimal('0'),
            'total_basic_salaries': Decimal('0'),
            'total_allowances': Decimal('0'),
            'total_additions': Decimal('0'),
            'total_deductions': Decimal('0'),
            'calculation_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'month': month,
            'year': year
        }

        # إحصائيات لكل نظام
        systems_statistics = {
            'monthly_system': {
                'employee_count': 0,
                'total_salaries': Decimal('0'),
                'total_additions': Decimal('0'),
                'total_deductions': Decimal('0'),
                'attendance_summary': {
                    'full_days': 0,
                    'half_days': 0,
                    'online_days': 0,
                    'excused_absences': 0,
                    'unexcused_absences': 0
                }
            },
            'production_system': {
                'employee_count': 0,
                'total_salaries': Decimal('0'),
                'total_production_value': Decimal('0'),
                'total_pieces': 0,
                'quality_summary': {
                    'A': {'count': 0, 'value': Decimal('0')},
                    'B': {'count': 0, 'value': Decimal('0')},
                    'C': {'count': 0, 'value': Decimal('0')},
                    'D': {'count': 0, 'value': Decimal('0')},
                    'E': {'count': 0, 'value': Decimal('0')}
                }
            },
            'shift_system': {
                'employee_count': 0,
                'total_salaries': Decimal('0'),
                'total_working_hours': 0,
                'total_overtime_hours': 0,
                'total_delay_minutes': 0,
                'total_break_minutes': 0
            }
        }

        # معالجة كل موظف
        for employee in employees:
            salary_result = calculate_employee_salary(employee, month, year)
            
            # تحديث الإحصائيات العامة
            general_statistics['total_basic_salaries'] += Decimal(salary_result['basic_salary'])
            general_statistics['total_allowances'] += Decimal(salary_result['allowances'])
            general_statistics['total_additions'] += Decimal(salary_result['additions'])
            general_statistics['total_deductions'] += Decimal(salary_result['deductions'])
            general_statistics['total_payroll'] += Decimal(salary_result['net_salary'])

            # تصنيف الموظف حسب نظام عمله
            if not employee.job_title:
               hourly_employees.append(salary_result)
            # تصنيف حسب النظام الفعلي فقط
            elif employee.job_title.month_system:
                monthly_system_employees.append(salary_result)
                update_monthly_system_statistics(systems_statistics['monthly_system'], salary_result)
            elif employee.job_title.production_system:
                production_system_employees.append(salary_result)
                update_production_system_statistics(systems_statistics['production_system'], salary_result)
            elif employee.job_title.shift_system:
                shift_system_employees.append(salary_result)
                update_shift_system_statistics(systems_statistics['shift_system'], salary_result)
            else:
                hourly_employees.append(salary_result)

        # تحديث عدد الموظفين في كل نظام
        systems_statistics['monthly_system']['employee_count'] = len(monthly_system_employees)
        systems_statistics['production_system']['employee_count'] = len(production_system_employees)
        systems_statistics['shift_system']['employee_count'] = len(shift_system_employees)

        # تنسيق القيم العشرية إلى نصوص
        format_decimal_values(general_statistics)
        format_system_statistics(systems_statistics)

        # تجميع النتيجة النهائية
        result = {
            'general_statistics': general_statistics,
            'systems_statistics': systems_statistics,
            'employees_by_system': {
                'monthly_system': monthly_system_employees,
                'production_system': production_system_employees,
                'shift_system': shift_system_employees,
                'hourly_employees': hourly_employees
            }
        }

        return jsonify(result), 200

    except Exception as e:
        print(f"Error in calculate_monthly_payroll: {str(e)}")
        return jsonify({'message': f'Error calculating payroll: {str(e)}'}), 500
    
def update_monthly_system_statistics(stats, salary_result):
    """تحديث إحصائيات النظام الشهري"""
    stats['total_salaries'] += Decimal(salary_result['net_salary'])
    stats['total_additions'] += Decimal(salary_result['additions'])
    stats['total_deductions'] += Decimal(salary_result['deductions'])
    
    if 'system_details' in salary_result:
        attendance = salary_result['system_details']
        stats['attendance_summary']['full_days'] += attendance.get('full_days', 0)
        stats['attendance_summary']['half_days'] += attendance.get('half_days', 0)
        stats['attendance_summary']['online_days'] += attendance.get('online_days', 0)
        stats['attendance_summary']['excused_absences'] += attendance.get('excused_absences', 0)
        stats['attendance_summary']['unexcused_absences'] += attendance.get('unexcused_absences', 0)


def update_production_system_statistics(stats, salary_result):
    """تحديث إحصائيات نظام الإنتاج"""
    stats['total_salaries'] += Decimal(salary_result['net_salary'])
    
    if 'system_details' in salary_result:
        production = salary_result['system_details']
        stats['total_production_value'] += Decimal(production.get('total_value', '0'))
        stats['total_pieces'] += production.get('total_pieces', 0)
        
        # تحديث ملخص الجودة
        for grade in 'ABCDE':
            if 'quality_summary' in production and grade in production['quality_summary']:
                grade_stats = production['quality_summary'][grade]
                stats['quality_summary'][grade]['count'] += grade_stats.get('count', 0)
                stats['quality_summary'][grade]['value'] += Decimal(str(grade_stats.get('value', '0')))

def update_shift_system_statistics(stats, salary_result):
    """تحديث إحصائيات نظام الورديات"""
    stats['total_salaries'] += Decimal(salary_result['net_salary'])
    
    if 'system_details' in salary_result:
        shift = salary_result['system_details']
        stats['total_working_hours'] += shift.get('total_working_minutes', 0) // 60
        stats['total_overtime_hours'] += shift.get('total_overtime_minutes', 0) // 60
        stats['total_delay_minutes'] += shift.get('total_delay_minutes', 0)
        stats['total_break_minutes'] += shift.get('total_break_minutes', 0)

def format_decimal_values(statistics):
    """تنسيق القيم العشرية إلى نصوص"""
    for key in statistics:
        if isinstance(statistics[key], Decimal):
            statistics[key] = str(statistics[key])

def format_system_statistics(systems_stats):
    """تنسيق إحصائيات الأنظمة"""
    for system in systems_stats.values():
        for key, value in system.items():
            if isinstance(value, Decimal):
                system[key] = str(value)
            elif isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, dict):
                        for k, v in sub_value.items():
                            if isinstance(v, Decimal):
                                sub_value[k] = str(v)


def calculate_employee_salary(employee, month, year):
    """حساب راتب موظف واحد"""
    try:
        # القيم الأساسية
        basic_salary = Decimal(str(employee.salary or 0))
        allowances = Decimal(str(employee.allowances or 0))
        insurance_deduction = Decimal(str(employee.insurance_deduction or 0))
        
        total_additions = Decimal('0')
        total_deductions = insurance_deduction
        notes = []
        system_details = {}
        system_type = 'none'

        # التحقق من نوع الموظف (بمسمى وظيفي أو بمهنة)
        if employee.profession and not employee.job_title:
            # موظف بنظام الساعات
            hourly_result = calculate_hourly_system(employee, month, year)
            total_additions += Decimal(str(hourly_result.get('additions', '0')))
            total_deductions += Decimal(str(hourly_result.get('deductions', '0')))
            system_details = hourly_result.get('details', {})
            system_type = 'hourly'
            notes.append(hourly_result.get('notes', ''))
        elif employee.job_title:
            # موظف بمسمى وظيفي - حساب حسب نوع النظام
            if employee.job_title.month_system:
                monthly_result = calculate_monthly_system(employee, month, year)
                total_additions += Decimal(str(monthly_result.get('additions', '0')))
                total_deductions += Decimal(str(monthly_result.get('deductions', '0')))
                system_details = monthly_result.get('details', {})
                system_type = 'monthly'
                notes.append(monthly_result.get('notes', ''))
            elif employee.job_title.production_system:
                production_result = calculate_production_system(employee, month, year)
                total_additions += Decimal(str(production_result.get('additions', '0')))
                system_details = production_result.get('details', {})
                system_type = 'production'
                notes.append(production_result.get('notes', ''))
            elif employee.job_title.shift_system:
                shift_result = calculate_shift_system(employee, month, year)
                total_additions += Decimal(str(shift_result.get('additions', '0')))
                total_deductions += Decimal(str(shift_result.get('deductions', '0')))
                system_details = shift_result.get('details', {})
                system_type = 'shift'
                notes.append(shift_result.get('notes', ''))
            elif employee.job_title.shift_system:
                shift_result = calculate_shift_system(employee, month, year)
                total_additions += Decimal(str(shift_result.get('additions', '0')))
                total_deductions += Decimal(str(shift_result.get('deductions', '0')))
                system_details = shift_result.get('details', {})
                system_type = 'shift'
                notes.append(shift_result.get('notes', ''))
        else:
            return create_basic_result(
                employee, basic_salary, allowances, 
                total_additions, total_deductions,
                "لا يوجد مسمى وظيفي أو مهنة"
            )

        # حساب السلف
        advances_result = calculate_advances(employee, month, year)
        advance_amount = Decimal(str(advances_result.get('amount', '0')))
        total_deductions += advance_amount

        if advance_amount > 0:
            notes.append(advances_result.get('notes', ''))

        # حساب صافي الراتب
        net_salary = basic_salary + allowances + total_additions - total_deductions

        # إنشاء النتيجة النهائية
        result = {
            'employee_id': employee.id,
            'employee_name': employee.full_name,
            'fingerprint_id': employee.fingerprint_id,
            'position': employee.job_title.title_name if employee.job_title else (
                employee.profession.name if employee.profession else 'غير محدد'
            ),
            'system_type': system_type,
            'basic_salary': str(basic_salary),
            'allowances': str(allowances),
            'additions': str(total_additions),
            'deductions': str(total_deductions),
            'net_salary': str(net_salary),
            'notes': " | ".join(filter(None, notes)),
            'calculation_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'system_details': system_details
        }

        # إضافة تفاصيل السلف إذا وجدت
        if advance_amount > 0:
            result['advances'] = advances_result.get('details', [])

        return result

    except Exception as e:
        print(f"Error in calculate_employee_salary: {str(e)}")
        return create_basic_result(
            employee, basic_salary, allowances, 
            Decimal('0'), insurance_deduction,
            f"خطأ في حساب الراتب: {str(e)}"
        )
    
def create_basic_result(employee, basic_salary, allowances, additions, deductions, notes):
    """إنشاء نتيجة أساسية للراتب"""
    net_salary = basic_salary + allowances + additions - deductions
    return {
        'employee_id': employee.id,
        'employee_name': employee.full_name,
        'fingerprint_id': employee.fingerprint_id,
        'position': employee.job_title.title_name if employee.job_title else 'غير محدد',
        'basic_salary': str(basic_salary),
        'allowances': str(allowances),
        'additions': str(additions),
        'deductions': str(deductions),
        'net_salary': str(net_salary),
        'notes': notes,
        'calculation_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
def calculate_monthly_system(employee, month, year):
    """حساب راتب النظام الشهري مع معالجة خاصة للغياب"""
    try:
        attendances = MonthlyAttendance.query.filter(
            MonthlyAttendance.employee_id == employee.id,
            extract('month', MonthlyAttendance.date) == month,
            extract('year', MonthlyAttendance.date) == year
        ).all()

        monthly_salary = Decimal(str(employee.salary or 0))
        daily_rate = monthly_salary / Decimal('30')

        total_amount = Decimal('0')
        deductions = Decimal('0')
        attendance_details = {
            'full_days': 0,
            'half_days': 0,
            'online_days': 0,
            'excused_absences': 0,
            'unexcused_absences': 0,
            'missing_days': 0,
            'daily_rate': str(daily_rate)
        }

        for attendance in attendances:
            if attendance.attendance_type == AttendanceType.FULL_DAY:
                total_amount += daily_rate
                attendance_details['full_days'] += 1
            elif attendance.attendance_type in [AttendanceType.HALF_DAY, AttendanceType.ONLINE_DAY]:
                total_amount += (daily_rate / Decimal('2'))
                if attendance.attendance_type == AttendanceType.HALF_DAY:
                    attendance_details['half_days'] += 1
                else:
                    attendance_details['online_days'] += 1
            elif attendance.attendance_type == AttendanceType.ABSENT:
                if attendance.is_excused_absence:
                    deductions += daily_rate
                    attendance_details['excused_absences'] += 1
                else:
                    deductions += (daily_rate * Decimal('2'))
                    attendance_details['unexcused_absences'] += 1

        # معالجة الأيام المفقودة
        missing_days = 30 - sum([
            attendance_details['full_days'],
            attendance_details['half_days'],
            attendance_details['online_days'],
            attendance_details['excused_absences'],
            attendance_details['unexcused_absences']
        ])
        
        if missing_days > 0:
            deductions += (daily_rate * Decimal('2') * Decimal(str(missing_days)))
            attendance_details['missing_days'] = missing_days
            attendance_details['unexcused_absences'] += missing_days

        # إضافة المبالغ المحسوبة للتفاصيل
        attendance_details.update({
            'total_amount': str(total_amount),
            'total_deductions': str(deductions),
            'net_amount': str(total_amount - deductions)
        })

        return {
            'additions': total_amount,
            'deductions': deductions,
            'details': attendance_details,
            'notes': (
                f"أيام كاملة: {attendance_details['full_days']}, "
                f"أنصاف أيام: {attendance_details['half_days']}, "
                f"أيام أونلاين: {attendance_details['online_days']}, "
                f"غياب بعذر: {attendance_details['excused_absences']} (خصم {attendance_details['excused_absences']} يوم), "
                f"غياب بدون عذر: {attendance_details['unexcused_absences']} (خصم {attendance_details['unexcused_absences'] * 2} يوم)"
            )
        }

    except Exception as e:
        raise Exception(f"Error in monthly system calculation: {str(e)}")

def calculate_advances(employee, month, year):
    """حساب السلف"""
    try:
        advances = Advance.query.filter(
            Advance.employee_id == employee.id,
            extract('month', Advance.date) == month,
            extract('year', Advance.date) == year
        ).all()

        total_advances = sum(Decimal(str(advance.amount)) for advance in advances)
        
        advance_details = [{
            'date': advance.date.strftime('%Y-%m-%d'),
            'amount': str(advance.amount),
            'document_number': advance.document_number,
            'notes': advance.notes
        } for advance in advances]

        return {
            'amount': total_advances,
            'details': advance_details,
            'notes': f"إجمالي السلف: {total_advances}" if total_advances > 0 else ""
        }

    except Exception as e:
        raise Exception(f"Error calculating advances: {str(e)}")

def create_salary_result(employee, basic_salary, allowances, additions, deductions, net_salary, notes, details):
    """إنشاء كائن نتيجة الراتب مع تفاصيل كاملة"""
    return {
        'employee_id': employee.id,
        'employee_name': employee.full_name,
        'fingerprint_id': employee.fingerprint_id,
        'position': employee.job_title.title_name if employee.job_title else 'غير محدد',
        'basic_salary': str(basic_salary),
        'allowances': str(allowances),
        'additions': str(additions),
        'deductions': str(deductions),
        'net_salary': str(net_salary),
        'notes': notes,
        'details': details,
        'calculation_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }


def calculate_production_system(employee, month, year):
    """حساب راتب نظام الإنتاج مع التفاصيل الكاملة لكل مستوى جودة"""
    try:
        # جلب سجلات الإنتاج للموظف في الشهر المحدد
        production_records = ProductionMonitoring.query.filter(
            ProductionMonitoring.employee_id == employee.id,
            extract('month', ProductionMonitoring.date) == month,
            extract('year', ProductionMonitoring.date) == year
        ).all()

        # تهيئة المتغيرات للحساب
        total_production_value = Decimal('0')
        production_details = {
            'pieces': [],
            'quality_summary': {
                'A': {'count': 0, 'value': Decimal('0')},
                'B': {'count': 0, 'value': Decimal('0')},
                'C': {'count': 0, 'value': Decimal('0')},
                'D': {'count': 0, 'value': Decimal('0')},
                'E': {'count': 0, 'value': Decimal('0')}
            },
            'total_pieces': 0,
            'total_value': Decimal('0'),
            'daily_production': {}
        }

        # معالجة كل سجل إنتاج
        for record in production_records:
            piece = record.piece
            date = record.date.strftime('%Y-%m-%d')
            quality_grade = record.quality_grade
            quantity = record.quantity
            
            # جلب سعر القطعة حسب مستوى الجودة
            price_levels = piece.price_levels
            piece_price = Decimal(str(price_levels.get(quality_grade, 0)))
            piece_total_value = piece_price * Decimal(str(quantity))

            # إضافة قيمة الإنتاج للمجموع
            total_production_value += piece_total_value
            
            # تحديث ملخص الجودة
            production_details['quality_summary'][quality_grade]['count'] += quantity
            production_details['quality_summary'][quality_grade]['value'] += piece_total_value
            
            # تحديث إجمالي القطع
            production_details['total_pieces'] += quantity

            # تجميع الإنتاج اليومي
            if date not in production_details['daily_production']:
                production_details['daily_production'][date] = {
                    'pieces': [],
                    'total_value': Decimal('0'),
                    'total_pieces': 0
                }

            # إضافة تفاصيل القطعة
            piece_details = {
                'piece_id': piece.id,
                'piece_number': piece.piece_number,
                'piece_name': piece.piece_name,
                'quantity': quantity,
                'quality_grade': quality_grade,
                'price': str(piece_price),
                'total_value': str(piece_total_value),
                'notes': record.notes
            }

            production_details['pieces'].append(piece_details)
            production_details['daily_production'][date]['pieces'].append(piece_details)
            production_details['daily_production'][date]['total_value'] += piece_total_value
            production_details['daily_production'][date]['total_pieces'] += quantity

        # تحويل القيم العشرية إلى نصوص للـ JSON
        for grade in production_details['quality_summary']:
            production_details['quality_summary'][grade]['value'] = str(
                production_details['quality_summary'][grade]['value']
            )

        for date in production_details['daily_production']:
            production_details['daily_production'][date]['total_value'] = str(
                production_details['daily_production'][date]['total_value']
            )

        production_details['total_value'] = str(total_production_value)

        # إنشاء ملخص للملاحظات
        quality_summary_notes = []
        for grade in 'ABCDE':
            count = production_details['quality_summary'][grade]['count']
            if count > 0:
                value = production_details['quality_summary'][grade]['value']
                quality_summary_notes.append(f"جودة {grade}: {count} قطعة بقيمة {value}")

        notes = (
            f"إجمالي القطع: {production_details['total_pieces']}, "
            f"إجمالي القيمة: {total_production_value} | "
            f"{' | '.join(quality_summary_notes)}"
        )

        return {
            'additions': total_production_value,
            'notes': notes,
            'details': production_details
        }

    except Exception as e:
        raise Exception(f"Error in production system calculation: {str(e)}")
    
# شرح آلية حساب راتب نظام الورديات

"""
يتم حساب راتب نظام الورديات بناءً على عدة عوامل:

1. المسمى الوظيفي للموظف والذي يحدد:
   - وقت الاستراحة المسموح به (allowed_break_time)
   - قيمة ساعة العمل الإضافي (overtime_hour_value)
   - قيمة دقيقة التأخير (delay_minute_value)

2. الوردية المحددة للموظف والتي تحدد:
   - وقت بداية الدوام (start_time)
   - وقت نهاية الدوام (end_time)
   - الوقت المسموح للتأخير (allowed_delay_minutes)
   - الوقت المسموح للخروج المبكر (allowed_exit_minutes)

3. سجلات الحضور والانصراف والتي تشمل:
   - تواريخ وأوقات الدخول (checkInTime)
   - تواريخ وأوقات الخروج (checkOutTime)

خطوات الحساب:
"""



def calculate_shift_system(employee, month, year):
    """حساب راتب نظام الورديات مع معالجة فترات الدوام المتعددة والاستراحات"""
    try:
        # التحقق من وجود المسمى الوظيفي
        if not employee.job_title:
            return {
                'additions': Decimal('0'),
                'deductions': Decimal('0'),
                'details': {},
                'notes': "لا يوجد مسمى وظيفي للموظف"
            }

        # التحقق من وجود الوردية
        shift = None
        if hasattr(employee, 'shift_id') and employee.shift_id:
            shift = Shift.query.get(employee.shift_id)
        
        if not shift:
            return {
                'additions': Decimal('0'),
                'deductions': Decimal('0'),
                'details': {},
                'notes': "لا توجد وردية محددة للموظف"
            }

        # جلب سجلات الحضور مرتبة حسب التاريخ والوقت
        attendances = (Attendance.query
            .filter(
                Attendance.empId == employee.id,
                extract('month', Attendance.createdAt) == month,
                extract('year', Attendance.createdAt) == year
            )
            .order_by(Attendance.createdAt, Attendance.checkInTime)
            .all())

        if not attendances:
            return {
                'additions': Decimal('0'),
                'deductions': Decimal('0'),
                'details': {
                    'total_days': 0,
                    'total_working_minutes': 0,
                    'total_overtime_minutes': 0,
                    'total_delay_minutes': 0,
                    'total_excess_break_minutes': 0,
                    'daily_records': []
                },
                'notes': "لا توجد سجلات حضور للشهر المحدد"
            }

        # جلب إعدادات المسمى الوظيفي
        job_title = employee.job_title
        allowed_break_minutes = convert_time_to_minutes(job_title.allowed_break_time or "00:00")
        overtime_hour_value = Decimal(str(job_title.overtime_hour_value or 0))
        delay_minute_value = Decimal(str(job_title.delay_minute_value or 0))

        # تجميع السجلات حسب اليوم مع معالجة التواريخ بشكل صحيح
        daily_records = {}
        for attendance in attendances:
            try:
                # معالجة التاريخ بشكل آمن
                if isinstance(attendance.createdAt, datetime):
                    date = attendance.createdAt.date()
                else:
                    date = attendance.createdAt

                if date not in daily_records:
                    daily_records[date] = []
                daily_records[date].append(attendance)
            except Exception as e:
                print(f"Error processing attendance record: {str(e)}")
                continue

        # متغيرات لتجميع النتائج الشهرية
        total_working_minutes = 0
        total_overtime_minutes = 0
        total_delay_minutes = 0
        total_excess_break_minutes = 0
        monthly_details = []

        # معالجة كل يوم على حدة
        for date, day_attendances in daily_records.items():
            try:
                day_result = process_shift_day(
                    day_attendances,
                    shift,
                    allowed_break_minutes,
                    delay_minute_value
                )

                total_working_minutes += day_result['working_minutes']
                total_overtime_minutes += day_result['overtime_minutes']
                total_delay_minutes += day_result['delay_minutes']
                total_excess_break_minutes += day_result['excess_break_minutes']
                
                monthly_details.append({
                    'date': date.strftime('%Y-%m-%d'),
                    **day_result
                })
            except Exception as e:
                print(f"Error processing day {date}: {str(e)}")
                continue

        # حساب القيم المالية
        overtime_value = (Decimal(str(total_overtime_minutes)) / Decimal('60')) * overtime_hour_value
        delay_deductions = Decimal(str(total_delay_minutes)) * delay_minute_value
        break_deductions = Decimal(str(total_excess_break_minutes)) * delay_minute_value
        total_deductions = delay_deductions + break_deductions

        details = {
            'total_days': len(daily_records),
            'total_working_minutes': total_working_minutes,
            'total_overtime_minutes': total_overtime_minutes,
            'total_delay_minutes': total_delay_minutes,
            'total_excess_break_minutes': total_excess_break_minutes,
            'overtime_value': str(overtime_value),
            'delay_deductions': str(delay_deductions),
            'break_deductions': str(break_deductions),
            'daily_records': monthly_details,
            'shift_info': {
                'start_time': shift.start_time.strftime('%H:%M'),
                'end_time': shift.end_time.strftime('%H:%M'),
                'allowed_break_minutes': allowed_break_minutes,
                'allowed_delay_minutes': shift.allowed_delay_minutes,
                'allowed_exit_minutes': shift.allowed_exit_minutes
            }
        }

        return {
            'additions': overtime_value,
            'deductions': total_deductions,
            'details': details,
            'notes': (
                f"أيام العمل: {len(daily_records)}, "
                f"ساعات العمل: {total_working_minutes // 60}, "
                f"ساعات إضافي: {total_overtime_minutes // 60}, "
                f"دقائق تأخير: {total_delay_minutes}, "
                f"دقائق استراحة زائدة: {total_excess_break_minutes}"
            )
        }

    except Exception as e:
        print(f"Error in shift calculation: {str(e)}")
        raise Exception(f"Error in shift system calculation: {str(e)}")
    
def process_shift_day(attendances, shift, allowed_break_minutes, delay_minute_value):
    """
    معالجة سجلات الحضور ليوم واحد
    
    الخطوات:
    1. تحويل أوقات الوردية إلى دقائق
    2. تجميع فترات العمل
    3. حساب أوقات الاستراحة
    4. حساب التأخير والإضافي
    """
    try:
        # 1. تحويل أوقات الوردية إلى دقائق
        shift_start_minutes = time_to_minutes(shift.start_time)
        shift_end_minutes = time_to_minutes(shift.end_time)
        shift_duration = shift_end_minutes - shift_start_minutes
        
        # 2. تهيئة المتغيرات
        working_periods = []          # فترات العمل
        total_break_minutes = 0       # إجمالي وقت الاستراحة
        first_check_in = None        # أول تسجيل دخول
        last_check_out = None        # آخر تسجيل خروج

        # 3. معالجة كل سجل حضور
        for i, attendance in enumerate(attendances):
            if not attendance.checkInTime or not attendance.checkOutTime:
                continue

            # تحويل أوقات الحضور إلى دقائق
            check_in_minutes = time_to_minutes(attendance.checkInTime)
            check_out_minutes = time_to_minutes(attendance.checkOutTime)

            # تسجيل أول دخول وآخر خروج
            if first_check_in is None:
                first_check_in = check_in_minutes
            last_check_out = check_out_minutes

            # حساب مدة العمل في هذه الفترة
            period_duration = check_out_minutes - check_in_minutes
            if period_duration > 0:
                working_periods.append({
                    'start': check_in_minutes,
                    'end': check_out_minutes,
                    'duration': period_duration
                })

            # 4. حساب وقت الاستراحة بين الفترات
            if i < len(attendances) - 1 and attendances[i+1].checkInTime:
                next_check_in = time_to_minutes(attendances[i+1].checkInTime)
                break_duration = next_check_in - check_out_minutes
                if break_duration > 0:
                    total_break_minutes += break_duration

        # 5. حساب النتائج النهائية لليوم
        # إجمالي وقت العمل
        total_working_minutes = sum(period['duration'] for period in working_periods)
        
        # حساب التأخير
        delay_minutes = max(0, first_check_in - shift_start_minutes - shift.allowed_delay_minutes)
        
        # حساب الخروج المبكر
        early_exit_minutes = max(0, shift_end_minutes - last_check_out - shift.allowed_exit_minutes) if last_check_out else 0
        
        # حساب الوقت الإضافي
        overtime_minutes = max(0, total_working_minutes - shift_duration)
        
        # حساب الاستراحة الزائدة
        excess_break_minutes = max(0, total_break_minutes - allowed_break_minutes)

        # 6. إرجاع النتيجة
        return {
            'working_minutes': total_working_minutes,
            'overtime_minutes': overtime_minutes,
            'delay_minutes': delay_minutes + early_exit_minutes,
            'break_minutes': total_break_minutes,
            'excess_break_minutes': excess_break_minutes,
            'periods': working_periods,
            'first_check_in': minutes_to_time_str(first_check_in),
            'last_check_out': minutes_to_time_str(last_check_out)
        }

    except Exception as e:
        print(f"Error processing shift day: {str(e)}")
        raise

# الدوال المساعدة

def time_to_minutes(time_obj):
    """
    تحويل كائن الوقت إلى دقائق
    مثال: 14:30 -> 870 دقيقة
    """
    return time_obj.hour * 60 + time_obj.minute

def minutes_to_time_str(minutes):
    """
    تحويل الدقائق إلى نص يمثل الوقت
    مثال: 870 -> "14:30"
    """
    if minutes is None:
        return None
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"

def convert_time_to_minutes(time_str):
    """
    تحويل نص الوقت إلى دقائق
    مثال: "14:30" -> 870
    """
    try:
        hours, minutes = map(int, time_str.split(':'))
        return hours * 60 + minutes
    except:
        return 0


def calculate_time_difference(time1, time2):
    """حساب الفرق بين وقتين بالدقائق"""
    minutes1 = time1.hour * 60 + time1.minute
    minutes2 = time2.hour * 60 + time2.minute
    return abs(minutes2 - minutes1)


def calculate_deductions(employee, month, year):
    """حساب الخصومات والسلف"""
    try:
        insurance_deduction = Decimal(str(employee.insurance_deduction or 0))

        advances = Advance.query.filter(
            Advance.employee_id == employee.id,
            extract('month', Advance.date) == month,
            extract('year', Advance.date) == year
        ).all()

        total_advances = sum(Decimal(str(advance.amount)) for advance in advances)

        return insurance_deduction + total_advances

    except Exception as e:
        raise Exception(f"Error calculating deductions: {str(e)}")


def create_salary_result(employee, basic_salary, allowances, additions, deductions, net_salary, notes, details):
    """إنشاء كائن نتيجة الراتب مع تفاصيل نظام العمل المحدد فقط"""
    try:
        # إنشاء النتيجة الأساسية
        result = {
            'employee_id': employee.id,
            'employee_name': employee.full_name,
            'fingerprint_id': employee.fingerprint_id,
            'position': employee.job_title.title_name if employee.job_title else 'غير محدد',
            'system_type': details.get('type', 'none'),
            'basic_salary': str(basic_salary),
            'allowances': str(allowances),
            'additions': str(additions),
            'deductions': str(deductions),
            'net_salary': str(net_salary),
            'notes': notes,
            'calculation_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        # إضافة تفاصيل حسب نوع النظام
        if details.get('type') == 'monthly' and 'attendance' in details:
            result['system_details'] = details['attendance']
        elif details.get('type') == 'production' and 'production' in details:
            result['system_details'] = details['production']
        elif details.get('type') == 'shift' and 'shift' in details:
            result['system_details'] = details['shift']

        # إضافة تفاصيل السلف إذا وجدت
        if 'advances' in details:
            result['advances'] = details['advances']

        return result

    except Exception as e:
        print(f"Error creating salary result: {str(e)}")
        # إرجاع نتيجة أساسية في حالة حدوث خطأ
        return {
            'employee_id': employee.id,
            'employee_name': employee.full_name,
            'basic_salary': str(basic_salary),
            'allowances': str(allowances),
            'additions': str(additions),
            'deductions': str(deductions),
            'net_salary': str(net_salary),
            'notes': f"Error processing details: {str(e)}"
        }
    

def calculate_hourly_system(employee, month, year):
    """حساب راتب نظام الساعات"""
    try:
        # التحقق من وجود المهنة
        if not employee.profession:
            return {
                'additions': Decimal('0'),
                'deductions': Decimal('0'),
                'details': {},
                'notes': "لا توجد مهنة محددة للموظف"
            }

        # جلب سجلات الحضور مرتبة حسب التاريخ والوقت
        attendances = (Attendance.query
            .filter(
                Attendance.empId == employee.id,
                extract('month', Attendance.createdAt) == month,
                extract('year', Attendance.createdAt) == year
            )
            .order_by(Attendance.createdAt, Attendance.checkInTime)
            .all())

        if not attendances:
            return {
                'additions': Decimal('0'),
                'deductions': Decimal('0'),
                'details': {
                    'total_days': 0,
                    'total_hours': 0,
                    'total_amount_by_hours': Decimal('0'),
                    'total_amount_by_days': Decimal('0'),
                    'daily_records': []
                },
                'notes': "لا توجد سجلات حضور للشهر المحدد"
            }

        # جلب معدلات الأجور من المهنة
        hourly_rate = Decimal(str(employee.profession.hourly_rate))
        daily_rate = Decimal(str(employee.profession.daily_rate))

        # تجميع السجلات حسب اليوم
        daily_records = {}
        for attendance in attendances:
            try:
                date = attendance.createdAt.date()
                if date not in daily_records:
                    daily_records[date] = []
                daily_records[date].append(attendance)
            except Exception as e:
                print(f"Error processing attendance record: {str(e)}")
                continue

        # متغيرات لتجميع النتائج الشهرية
        total_working_hours = Decimal('0')
        monthly_details = []
        total_days = len(daily_records)

        # معالجة كل يوم على حدة
        for date, day_attendances in daily_records.items():
            day_total_hours = Decimal('0')
            day_records = []

            # حساب ساعات العمل لكل فترة في اليوم
            for attendance in day_attendances:
                if attendance.checkInTime and attendance.checkOutTime:
                    hours = calculate_hours_worked(attendance.checkInTime, attendance.checkOutTime)
                    day_total_hours += hours
                    day_records.append({
                        'check_in': attendance.checkInTime.strftime('%H:%M'),
                        'check_out': attendance.checkOutTime.strftime('%H:%M'),
                        'hours': str(hours)
                    })

            # إضافة تفاصيل اليوم
            day_amount_by_hours = day_total_hours * hourly_rate
            monthly_details.append({
                'date': date.strftime('%Y-%m-%d'),
                'total_hours': str(day_total_hours),
                'amount_by_hours': str(day_amount_by_hours),
                'amount_by_day': str(daily_rate),
                'periods': day_records
            })
            total_working_hours += day_total_hours

        # حساب المبلغ الإجمالي
        total_amount_by_hours = total_working_hours * hourly_rate
        total_amount_by_days = Decimal(str(total_days)) * daily_rate

        # اختيار المبلغ الأعلى بين الحساب بالساعات والحساب بالأيام
        total_amount = max(total_amount_by_hours, total_amount_by_days)

        details = {
            'total_days': total_days,
            'total_hours': str(total_working_hours),
            'hourly_rate': str(hourly_rate),
            'daily_rate': str(daily_rate),
            'total_amount_by_hours': str(total_amount_by_hours),
            'total_amount_by_days': str(total_amount_by_days),
            'daily_records': monthly_details
        }

        return {
            'additions': total_amount,
            'deductions': Decimal('0'),
            'details': details,
            'notes': (
                f"أيام العمل: {total_days}, "
                f"ساعات العمل: {total_working_hours}, "
                f"المبلغ حسب الساعات: {total_amount_by_hours}, "
                f"المبلغ حسب الأيام: {total_amount_by_days}"
            )
        }

    except Exception as e:
        print(f"Error in hourly system calculation: {str(e)}")
        raise Exception(f"Error in hourly system calculation: {str(e)}")

def calculate_hours_worked(check_in, check_out):
    """حساب عدد ساعات العمل بين وقتين"""
    try:
        check_in_minutes = check_in.hour * 60 + check_in.minute
        check_out_minutes = check_out.hour * 60 + check_out.minute
        total_minutes = check_out_minutes - check_in_minutes
        return Decimal(str(total_minutes)) / Decimal('60')
    except Exception as e:
        print(f"Error calculating hours worked: {str(e)}")
        return Decimal('0')