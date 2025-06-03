from flask import Blueprint, request, jsonify
from datetime import datetime, date, timedelta
from sqlalchemy import extract, and_
from decimal import Decimal
from app import db
from app.models import AttendanceType, Employee, JobTitle, MonthlyAttendance, Attendance, ProductionMonitoring, Advance, Shift, user
from app.utils import token_required

payroll_bp = Blueprint('payroll', __name__)


# إضافة enum لتحديد نوع الراتب
class SalaryType:
    MONTHLY = 'monthly'
    WEEKLY = 'weekly'



@payroll_bp.route('/api/payroll/calculate-period', methods=['POST'])
@token_required
def calculate_period_payroll(user):
    """
    حساب الرواتب لفترة محددة بين تاريخين مع دعم الراتب الشهري والأسبوعي
    """
    try:
        # التحقق من صحة المستخدم
        user = user.query.get(user.id)
        if not user:
            return {'message': 'User not found'}, 404

        data = request.get_json()
        required_fields = ['start_date', 'end_date']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({'message': f'Missing fields: {", ".join(missing_fields)}'}), 400

        # تحديد نوع الراتب (افتراضياً شهري للحفاظ على التوافق مع النظام الحالي)
        salary_type = data.get('salary_type', SalaryType.MONTHLY)
        if salary_type not in [SalaryType.MONTHLY, SalaryType.WEEKLY]:
            return jsonify({'message': 'Invalid salary_type. Must be "monthly" or "weekly"'}), 400

        # تحويل التواريخ
        try:
            start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'message': 'Invalid date format. Use YYYY-MM-DD'}), 400

        # التحقق من صحة الفترة
        if start_date > end_date:
            return jsonify({'message': 'Start date cannot be after end date'}), 400

        if end_date > date.today() + timedelta(days=1):
            return jsonify({'message': 'End date cannot be in the future'}), 400

        # حساب عدد الأيام في الفترة
        period_days = (end_date - start_date).days + 1

        # جلب جميع الموظفين
        employees = user.get_accessible_employees()

        # تهيئة المتغيرات لتجميع النتائج
        monthly_system_employees = []
        production_system_employees = []
        shift_system_employees = []
        hourly_employees = []

        # إحصائيات عامة مع إضافة معلومات الخروج المبكر
        general_statistics = {
            'total_employees': len(employees),
            'total_payroll': Decimal('0'),
            'total_basic_salaries': Decimal('0'),
            'total_allowances': Decimal('0'),
            'total_additions': Decimal('0'),
            'total_deductions': Decimal('0'),
            'calculation_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'salary_type': salary_type,
            'period': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'total_days': period_days
            },
            'delay_statistics': {
                'total_employees_with_delays': 0,
                'total_delay_hours': 0,
                'total_delay_minutes': 0,
                'average_delay_per_employee': '00:00',
                # إضافة إحصائيات الخروج المبكر
                'total_employees_with_early_exit': 0,
                'total_early_exit_hours': 0,
                'total_early_exit_minutes': 0,
                'average_early_exit_per_employee': '00:00',
                # إحصائيات المخالفات الإجمالية
                'total_employees_with_violations': 0,
                'total_violation_hours': 0,
                'total_violation_minutes': 0,
                'average_violation_per_employee': '00:00'
            }
        }

        # إحصائيات لكل نظام (نفس الكود الأصلي)
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
        
        # متغيرات لحساب الإحصائيات الجديدة
        total_delay_minutes_all = 0
        total_early_exit_minutes_all = 0
        total_violation_minutes_all = 0
        employees_with_delays = 0
        employees_with_early_exit = 0
        employees_with_violations = 0

        # معالجة كل موظف مع تمرير نوع الراتب
        for employee in employees:
            salary_result = calculate_employee_salary_period(employee, start_date, end_date, salary_type)
            
            # تحديث الإحصائيات العامة
            general_statistics['total_basic_salaries'] += Decimal(salary_result['basic_salary'])
            general_statistics['total_allowances'] += Decimal(salary_result['allowances'])
            general_statistics['total_additions'] += Decimal(salary_result['additions'])
            general_statistics['total_deductions'] += Decimal(salary_result['deductions'])
            general_statistics['total_payroll'] += Decimal(salary_result['net_salary'])

            # حساب إحصائيات التأخير والخروج المبكر
            if 'delay_info' in salary_result and salary_result['delay_info']:
                delay_info = salary_result['delay_info']
                
                # إحصائيات التأخير
                if delay_info.get('total_delay_minutes', 0) > 0:
                    employees_with_delays += 1
                    total_delay_minutes_all += delay_info['total_delay_minutes']
                
                # إحصائيات الخروج المبكر
                if delay_info.get('early_exit_minutes', 0) > 0:
                    employees_with_early_exit += 1
                    total_early_exit_minutes_all += delay_info['early_exit_minutes']
                
                # إحصائيات المخالفات الإجمالية
                if delay_info.get('total_violation_minutes', 0) > 0:
                    employees_with_violations += 1
                    total_violation_minutes_all += delay_info['total_violation_minutes']

            # تصنيف الموظف حسب نظام عمله
            if not employee.job_title:
               hourly_employees.append(salary_result)
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

        # تحديث إحصائيات التأخير والخروج المبكر العامة
        delay_stats = general_statistics['delay_statistics']
        
        # إحصائيات التأخير
        delay_stats['total_employees_with_delays'] = employees_with_delays
        delay_stats['total_delay_hours'] = total_delay_minutes_all // 60
        delay_stats['total_delay_minutes'] = total_delay_minutes_all % 60
        
        # إحصائيات الخروج المبكر
        delay_stats['total_employees_with_early_exit'] = employees_with_early_exit
        delay_stats['total_early_exit_hours'] = total_early_exit_minutes_all // 60
        delay_stats['total_early_exit_minutes'] = total_early_exit_minutes_all % 60
        
        # إحصائيات المخالفات الإجمالية
        delay_stats['total_employees_with_violations'] = employees_with_violations
        delay_stats['total_violation_hours'] = total_violation_minutes_all // 60
        delay_stats['total_violation_minutes'] = total_violation_minutes_all % 60
        
        # حساب المتوسطات
        if employees_with_delays > 0:
            avg_delay_minutes = total_delay_minutes_all // employees_with_delays
            avg_hours = avg_delay_minutes // 60
            avg_mins = avg_delay_minutes % 60
            delay_stats['average_delay_per_employee'] = f"{avg_hours:02d}:{avg_mins:02d}"
        
        if employees_with_early_exit > 0:
            avg_early_exit_minutes = total_early_exit_minutes_all // employees_with_early_exit
            avg_hours = avg_early_exit_minutes // 60
            avg_mins = avg_early_exit_minutes % 60
            delay_stats['average_early_exit_per_employee'] = f"{avg_hours:02d}:{avg_mins:02d}"
        
        if employees_with_violations > 0:
            avg_violation_minutes = total_violation_minutes_all // employees_with_violations
            avg_hours = avg_violation_minutes // 60
            avg_mins = avg_violation_minutes % 60
            delay_stats['average_violation_per_employee'] = f"{avg_hours:02d}:{avg_mins:02d}"
            
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
        print(f"Error in calculate_period_payroll: {str(e)}")
        return jsonify({'message': f'Error calculating payroll: {str(e)}'}), 500


def calculate_employee_salary_period(employee, start_date, end_date, salary_type=SalaryType.MONTHLY):
    """حساب راتب موظف واحد لفترة محددة مع دعم الراتب الشهري والأسبوعي"""
    try:
        # حساب عدد الأيام في الفترة
        period_days = (end_date - start_date).days + 1
        
        # القيم الأساسية
        basic_salary = Decimal(str(employee.salary or 0))
        allowances = Decimal(str(employee.allowances or 0))
        
        # حساب الراتب الأساسي والبدلات بشكل نسبي للفترة حسب نوع الراتب
        period_basic_salary = calculate_proportional_salary(basic_salary, start_date, end_date, salary_type)
        period_allowances = calculate_proportional_allowances(allowances, start_date, end_date, salary_type)
        
        # التحقق من صلاحية التأمينات للفترة
        insurance_deduction = calculate_insurance_for_period(employee, start_date, end_date, salary_type)
        
        # حساب معلومات التأخير والخروج المبكر
        delay_info = calculate_employee_delay_info(employee, start_date, end_date)

        total_additions = Decimal('0')
        total_deductions = insurance_deduction
        notes = []
        system_details = {}
        system_type = 'none'
        
        # إضافة ملاحظة حول التأمينات
        if insurance_deduction > 0:
            notes.append(f"التأمينات للفترة: {insurance_deduction}")
        
        # إضافة ملاحظة حول نوع الراتب
        salary_type_note = "راتب شهري" if salary_type == SalaryType.MONTHLY else "راتب أسبوعي"
        notes.append(f"نوع الراتب: {salary_type_note}")

        # التحقق من نوع الموظف وحساب الراتب حسب النظام
        if employee.profession and not employee.job_title:
            # موظف بنظام الساعات
            hourly_result = calculate_hourly_system_period(employee, start_date, end_date, salary_type)
            total_additions += Decimal(str(hourly_result.get('additions', '0')))
            total_deductions += Decimal(str(hourly_result.get('deductions', '0')))
            system_details = hourly_result.get('details', {})
            system_type = 'hourly'
            notes.append(hourly_result.get('notes', ''))
        elif employee.job_title:
            # موظف بمسمى وظيفي - حساب حسب نوع النظام
            if employee.job_title.month_system:
                monthly_result = calculate_monthly_system_period(employee, start_date, end_date, salary_type)
                total_additions += Decimal(str(monthly_result.get('additions', '0')))
                total_deductions += Decimal(str(monthly_result.get('deductions', '0')))
                system_details = monthly_result.get('details', {})
                system_type = 'monthly'
                notes.append(monthly_result.get('notes', ''))
            elif employee.job_title.production_system:
                production_result = calculate_production_system_period(employee, start_date, end_date, salary_type)
                total_additions += Decimal(str(production_result.get('additions', '0')))
                system_details = production_result.get('details', {})
                system_type = 'production'
                notes.append(production_result.get('notes', ''))
            elif employee.job_title.shift_system:
                shift_result = calculate_shift_system_period(employee, start_date, end_date, salary_type)
                total_additions += Decimal(str(shift_result.get('additions', '0')))
                total_deductions += Decimal(str(shift_result.get('deductions', '0')))
                system_details = shift_result.get('details', {})
                system_type = 'shift'
                notes.append(shift_result.get('notes', ''))

        # حساب السلف للفترة
        advances_result = calculate_advances_period(employee, start_date, end_date)
        advance_amount = Decimal(str(advances_result.get('amount', '0')))
        total_deductions += advance_amount

        if advance_amount > 0:
            notes.append(advances_result.get('notes', ''))

        # إضافة ملاحظات التأخير والخروج المبكر
        if delay_info['total_delay_minutes'] > 0:
            notes.append(f"إجمالي التأخير: {delay_info['total_delay_formatted']}")
        
        if delay_info['early_exit_minutes'] > 0:
            notes.append(f"إجمالي الخروج المبكر: {delay_info['early_exit_formatted']}")
        
        if delay_info['total_violation_minutes'] > 0:
            notes.append(f"إجمالي المخالفات: {delay_info['total_violation_formatted']}")

        # حساب صافي الراتب
        net_salary = period_basic_salary + period_allowances + total_additions - total_deductions

        # إنشاء النتيجة النهائية
        result = {
            'employee_id': employee.id,
            'employee_name': employee.full_name,
            'fingerprint_id': employee.fingerprint_id,
            'position': employee.job_title.title_name if employee.job_title else (
                employee.profession.name if employee.profession else 'غير محدد'
            ),
            'system_type': system_type,
            'salary_type': salary_type,  # إضافة نوع الراتب للنتيجة
            'basic_salary': str(period_basic_salary),
            'allowances': str(period_allowances),
            'additions': str(total_additions),
            'deductions': str(total_deductions),
            'net_salary': str(net_salary),
            'notes': " | ".join(filter(None, notes)),
            'calculation_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'period_info': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'total_days': period_days
            },
            'system_details': system_details,
            'delay_info': delay_info
        }

        # إضافة تفاصيل السلف إذا وجدت
        if advance_amount > 0:
            result['advances'] = advances_result.get('details', [])

        return result

    except Exception as e:
        print(f"Error in calculate_employee_salary_period: {str(e)}")
        return create_basic_result_period(
            employee, period_basic_salary, period_allowances, 
            Decimal('0'), insurance_deduction,
            f"خطأ في حساب الراتب: {str(e)}", start_date, end_date, salary_type
        )
    
def calculate_proportional_salary(base_salary, start_date, end_date, salary_type=SalaryType.MONTHLY):
    """
    حساب الراتب الأساسي بشكل نسبي للفترة المحددة
    يدعم الراتب الشهري والأسبوعي
    """
    try:
        if salary_type == SalaryType.WEEKLY:
            return calculate_weekly_proportional_salary(base_salary, start_date, end_date)
        else:
            return calculate_monthly_proportional_salary(base_salary, start_date, end_date)
        
    except Exception as e:
        print(f"Error calculating proportional salary: {str(e)}")
        return base_salary

def calculate_weekly_proportional_salary(weekly_salary, start_date, end_date):
    """حساب الراتب بشكل نسبي بناءً على الراتب الأسبوعي"""
    try:
        # حساب عدد الأيام في الفترة
        total_days = (end_date - start_date).days + 1
        
        # حساب المعدل اليومي من الراتب الأسبوعي (7 أيام في الأسبوع)
        daily_rate = weekly_salary / Decimal('6')
        
        # حساب الراتب للفترة
        period_salary = daily_rate * Decimal(str(total_days))
        
        return period_salary
        
    except Exception as e:
        print(f"Error calculating weekly proportional salary: {str(e)}")
        return weekly_salary

def calculate_monthly_proportional_salary(monthly_salary, start_date, end_date):
    """حساب الراتب بشكل نسبي بناءً على الراتب الشهري (الكود الأصلي)"""
    try:
        # تحديد الشهر والسنة للحساب النسبي
        # إذا كانت الفترة تغطي أكثر من شهر، نحسب لكل شهر على حدة
        total_proportional_salary = Decimal('0')
        
        current_date = start_date
        while current_date <= end_date:
            # تحديد نهاية الشهر الحالي
            if current_date.month == 12:
                next_month = current_date.replace(year=current_date.year + 1, month=1, day=1)
            else:
                next_month = current_date.replace(month=current_date.month + 1, day=1)
            
            month_end = (next_month - timedelta(days=1))
            period_end_in_month = min(end_date, month_end)
            
            # حساب الأيام في هذا الشهر للفترة المحددة
            days_in_period = (period_end_in_month - current_date).days + 1
            days_in_month = month_end.day
            
            # حساب النسبة
            month_proportion = Decimal(str(days_in_period)) / Decimal(str(days_in_month))
            month_salary = monthly_salary * month_proportion
            
            total_proportional_salary += month_salary
            
            # الانتقال للشهر التالي
            current_date = next_month
            
        return total_proportional_salary
        
    except Exception as e:
        print(f"Error calculating monthly proportional salary: {str(e)}")
        return monthly_salary

def calculate_proportional_allowances(allowances, start_date, end_date, salary_type=SalaryType.MONTHLY):
    """حساب البدلات بشكل نسبي للفترة المحددة"""
    return calculate_proportional_salary(allowances, start_date, end_date, salary_type)

def calculate_insurance_for_period(employee, start_date, end_date, salary_type=SalaryType.MONTHLY):
    """حساب التأمينات للفترة المحددة مع دعم الراتب الأسبوعي"""
    try:
        if not hasattr(employee, 'insurance_deduction') or not employee.insurance_deduction:
            return Decimal('0')
            
        if not hasattr(employee, 'insurance_start_date') or not hasattr(employee, 'insurance_end_date'):
            return Decimal('0')
            
        if not employee.insurance_start_date or not employee.insurance_end_date:
            return Decimal('0')
        
        # تحديد تداخل فترة التأمين مع الفترة المطلوبة
        insurance_start = max(employee.insurance_start_date, start_date)
        insurance_end = min(employee.insurance_end_date, end_date)
        
        if insurance_start > insurance_end:
            return Decimal('0')  # لا يوجد تداخل
        
        # حساب التأمين بشكل نسبي حسب نوع الراتب
        insurance_amount = Decimal(str(employee.insurance_deduction))
        
        if salary_type == SalaryType.WEEKLY:
            # حساب التأمين على أساس أسبوعي
            insurance_days = (insurance_end - insurance_start).days + 1
            daily_insurance = insurance_amount / Decimal('6')  # تقسيم على 7 أيام
            return daily_insurance * Decimal(str(insurance_days))
        else:
            # الحساب الشهري الأصلي
            return calculate_proportional_salary(insurance_amount, insurance_start, insurance_end, salary_type)
        
    except Exception as e:
        print(f"Error calculating insurance for period: {str(e)}")
        return Decimal('0')

def calculate_monthly_system_period(employee, start_date, end_date, salary_type=SalaryType.MONTHLY):
    """حساب راتب النظام الشهري لفترة محددة مع دعم الراتب الأسبوعي"""
    try:
        attendances = MonthlyAttendance.query.filter(
            MonthlyAttendance.employee_id == employee.id,
            MonthlyAttendance.date.between(start_date, end_date)
        ).all()

        # حساب المعدل اليومي بناءً على نوع الراتب
        salary_amount = Decimal(str(employee.salary or 0))
        period_days = (end_date - start_date).days + 1
        
        if salary_type == SalaryType.WEEKLY:
            # حساب المعدل اليومي من الراتب الأسبوعي
            daily_rate = salary_amount / Decimal('6')
        else:
            # حساب المعدل اليومي من الراتب الشهري (استخدام 30 كمعيار)
            daily_rate = salary_amount / Decimal('30')

        total_amount = Decimal('0')
        deductions = Decimal('0')
        attendance_details = {
            'full_days': 0,
            'half_days': 0,
            'online_days': 0,
            'excused_absences': 0,
            'unexcused_absences': 0,
            'missing_days': 0,
            'daily_rate': str(daily_rate),
            'period_days': period_days,
            'salary_type': salary_type
        }

        # معالجة سجلات الحضور (نفس المنطق الأصلي)
        recorded_dates = set()
        for attendance in attendances:
            recorded_dates.add(attendance.date)
            
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

        # حساب الأيام المفقودة
        total_expected_days = period_days
        total_recorded_days = len(recorded_dates)
        missing_days = max(0, total_expected_days - total_recorded_days)
        
        if missing_days > 0:
            deductions += (daily_rate * Decimal('2') * Decimal(str(missing_days)))
            attendance_details['missing_days'] = missing_days
            attendance_details['unexcused_absences'] += missing_days

        attendance_details.update({
            'total_amount': str(total_amount),
            'total_deductions': str(deductions),
            'net_amount': str(total_amount - deductions)
        })

        salary_type_text = "أسبوعي" if salary_type == SalaryType.WEEKLY else "شهري"
        
        return {
            'additions': total_amount,
            'deductions': deductions,
            'details': attendance_details,
            'notes': (
                f"نوع الراتب: {salary_type_text} | "
                f"الفترة: {period_days} يوم | "
                f"أيام كاملة: {attendance_details['full_days']}, "
                f"أنصاف أيام: {attendance_details['half_days']}, "
                f"أيام أونلاين: {attendance_details['online_days']}, "
                f"غياب بعذر: {attendance_details['excused_absences']}, "
                f"غياب بدون عذر: {attendance_details['unexcused_absences']}"
            )
        }

    except Exception as e:
        raise Exception(f"Error in monthly system period calculation: {str(e)}")

def calculate_production_system_period(employee, start_date, end_date, salary_type=SalaryType.MONTHLY):
    """حساب راتب نظام الإنتاج لفترة محددة (لا يتأثر بنوع الراتب)"""
    try:
        # جلب سجلات الإنتاج للفترة المحددة
        production_records = ProductionMonitoring.query.filter(
            ProductionMonitoring.employee_id == employee.id,
            ProductionMonitoring.date.between(start_date, end_date)
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
            'daily_production': {},
            'period_info': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'total_days': (end_date - start_date).days + 1
            }
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

        period_days = (end_date - start_date).days + 1
        notes = (
            f"نظام الإنتاج | الفترة: {period_days} يوم | "
            f"إجمالي القطع: {production_details['total_pieces']}, "
            f"إجمالي القيمة: {total_production_value}"
        )
        
        if quality_summary_notes:
            notes += f" | {' | '.join(quality_summary_notes)}"

        return {
            'additions': total_production_value,
            'notes': notes,
            'details': production_details
        }

    except Exception as e:
        raise Exception(f"Error in production system period calculation: {str(e)}")

def calculate_shift_system_period(employee, start_date, end_date, salary_type=SalaryType.MONTHLY):
    """حساب راتب نظام الورديات لفترة محددة (لا يتأثر بنوع الراتب الأساسي)"""
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

        # جلب سجلات الحضور للفترة المحددة
        attendances = (Attendance.query
            .filter(
                Attendance.empId == employee.id,
                Attendance.createdAt.between(start_date, end_date)
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
                    'daily_records': [],
                    'period_info': {
                        'start_date': start_date.strftime('%Y-%m-%d'),
                        'end_date': end_date.strftime('%Y-%m-%d'),
                        'total_days': (end_date - start_date).days + 1
                    }
                },
                'notes': "لا توجد سجلات حضور للفترة المحددة"
            }

        # جلب إعدادات المسمى الوظيفي
        job_title = employee.job_title
        allowed_break_minutes = convert_time_to_minutes(job_title.allowed_break_time or "00:00")
        overtime_hour_value = Decimal(str(job_title.overtime_hour_value or 0))
        delay_minute_value = Decimal(str(job_title.delay_minute_value or 0))

        # تجميع السجلات حسب اليوم
        daily_records = {}
        for attendance in attendances:
            try:
                if isinstance(attendance.createdAt, datetime):
                    date = attendance.createdAt.date()
                else:
                    date = attendance.createdAt

                # التأكد من أن التاريخ ضمن الفترة المطلوبة
                if start_date <= date <= end_date:
                    if date not in daily_records:
                        daily_records[date] = []
                    daily_records[date].append(attendance)
            except Exception as e:
                print(f"Error processing attendance record: {str(e)}")
                continue

        # متغيرات لتجميع النتائج للفترة
        total_working_minutes = 0
        total_overtime_minutes = 0
        total_delay_minutes = 0
        total_excess_break_minutes = 0
        period_details = []

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
                
                period_details.append({
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

        period_days = (end_date - start_date).days + 1
        
        details = {
            'period_info': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'total_days': period_days
            },
            'total_days': len(daily_records),
            'total_working_minutes': total_working_minutes,
            'total_overtime_minutes': total_overtime_minutes,
            'total_delay_minutes': total_delay_minutes,
            'total_excess_break_minutes': total_excess_break_minutes,
            'overtime_value': str(overtime_value),
            'delay_deductions': str(delay_deductions),
            'break_deductions': str(break_deductions),
            'daily_records': period_details,
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
                f"نظام الورديات | الفترة: {period_days} يوم | "
                f"أيام العمل: {len(daily_records)}, "
                f"ساعات العمل: {total_working_minutes // 60}, "
                f"ساعات إضافي: {total_overtime_minutes // 60}, "
                f"دقائق تأخير: {total_delay_minutes}, "
                f"دقائق استراحة زائدة: {total_excess_break_minutes}"
            )
        }

    except Exception as e:
        print(f"Error in shift period calculation: {str(e)}")
        raise Exception(f"Error in shift system period calculation: {str(e)}")

def calculate_hourly_system_period(employee, start_date, end_date, salary_type=SalaryType.MONTHLY):
    """حساب راتب نظام الساعات لفترة محددة (لا يتأثر بنوع الراتب الأساسي)"""
    try:
        # التحقق من وجود المهنة
        if not employee.profession:
            return {
                'additions': Decimal('0'),
                'deductions': Decimal('0'),
                'details': {},
                'notes': "لا توجد مهنة محددة للموظف"
            }

        # جلب سجلات الحضور للفترة المحددة
        attendances = (Attendance.query
            .filter(
                Attendance.empId == employee.id,
                Attendance.createdAt.between(start_date, end_date)
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
                    'daily_records': [],
                    'period_info': {
                        'start_date': start_date.strftime('%Y-%m-%d'),
                        'end_date': end_date.strftime('%Y-%m-%d'),
                        'total_days': (end_date - start_date).days + 1
                    }
                },
                'notes': "لا توجد سجلات حضور للفترة المحددة"
            }

        # جلب معدلات الأجور من المهنة
        hourly_rate = Decimal(str(employee.profession.hourly_rate))
        daily_rate = Decimal(str(employee.profession.daily_rate))

        # تجميع السجلات حسب اليوم
        daily_records = {}
        for attendance in attendances:
            try:
                date = attendance.createdAt.date()
                # التأكد من أن التاريخ ضمن الفترة المطلوبة
                if start_date <= date <= end_date:
                    if date not in daily_records:
                        daily_records[date] = []
                    daily_records[date].append(attendance)
            except Exception as e:
                print(f"Error processing attendance record: {str(e)}")
                continue

        # متغيرات لتجميع النتائج للفترة
        total_working_hours = Decimal('0')
        period_details = []
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
            period_details.append({
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

        period_days = (end_date - start_date).days + 1
        
        details = {
            'period_info': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'total_days': period_days
            },
            'total_days': total_days,
            'total_hours': str(total_working_hours),
            'hourly_rate': str(hourly_rate),
            'daily_rate': str(daily_rate),
            'total_amount_by_hours': str(total_amount_by_hours),
            'total_amount_by_days': str(total_amount_by_days),
            'daily_records': period_details
        }

        return {
            'additions': total_amount,
            'deductions': Decimal('0'),
            'details': details,
            'notes': (
                f"نظام الساعات | الفترة: {period_days} يوم | "
                f"أيام العمل: {total_days}, "
                f"ساعات العمل: {total_working_hours}, "
                f"المبلغ حسب الساعات: {total_amount_by_hours}, "
                f"المبلغ حسب الأيام: {total_amount_by_days}"
            )
        }

    except Exception as e:
        print(f"Error in hourly system period calculation: {str(e)}")
        raise Exception(f"Error in hourly system period calculation: {str(e)}")


def calculate_advances_period(employee, start_date, end_date):
    """حساب السلف للفترة المحددة (لا يتأثر بنوع الراتب)"""
    try:
        advances = Advance.query.filter(
            Advance.employee_id == employee.id,
            Advance.date.between(start_date, end_date)
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
            'notes': f"إجمالي السلف للفترة: {total_advances}" if total_advances > 0 else ""
        }

    except Exception as e:
        raise Exception(f"Error calculating advances for period: {str(e)}")

# باقي الدوال المساعدة
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
        stats['total_break_minutes'] += shift.get('total_excess_break_minutes', 0)

def create_basic_result_period(employee, basic_salary, allowances, additions, deductions, notes, start_date, end_date, salary_type=SalaryType.MONTHLY):
    """إنشاء نتيجة أساسية للراتب للفترة المحددة مع دعم نوع الراتب"""
    net_salary = basic_salary + allowances + additions - deductions
    period_days = (end_date - start_date).days + 1
    delay_info = {
        'total_delay_minutes': 0,
        'total_delay_hours': 0,
        'remaining_minutes': 0,
        'total_delay_formatted': '00:00',
        'delay_days': 0,
        'early_exit_minutes': 0,
        'early_exit_hours': 0,
        'early_exit_formatted': '00:00',
        'early_exit_days': 0,
        'total_violation_minutes': 0,
        'total_violation_hours': 0,
        'total_violation_formatted': '00:00',
        'total_violation_days': 0
    }
    
    return {
        'employee_id': employee.id,
        'employee_name': employee.full_name,
        'fingerprint_id': employee.fingerprint_id,
        'position': employee.job_title.title_name if employee.job_title else 'غير محدد',
        'salary_type': salary_type,
        'basic_salary': str(basic_salary),
        'allowances': str(allowances),
        'additions': str(additions),
        'deductions': str(deductions),
        'net_salary': str(net_salary),
        'notes': notes,
        'calculation_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'period_info': {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'total_days': period_days
        },
        'delay_info': delay_info
    }


def calculate_employee_delay_info(employee, start_date, end_date):
    """
    حساب معلومات التأخير والخروج المبكر للموظف في الفترة المحددة
    """
    try:
        delay_info = {
            'total_delay_minutes': 0,
            'total_delay_hours': 0,
            'remaining_minutes': 0,
            'total_delay_formatted': '00:00',
            'delay_days': 0,
            # إضافة معلومات الخروج المبكر
            'early_exit_minutes': 0,
            'early_exit_hours': 0,
            'early_exit_formatted': '00:00',
            'early_exit_days': 0,
            # إجمالي التأخير + الخروج المبكر
            'total_violation_minutes': 0,
            'total_violation_hours': 0,
            'total_violation_formatted': '00:00',
            'total_violation_days': 0
        }

        # الحصول على معلومات الوردية إذا كان الموظف في نظام الورديات
        shift = None
        if (hasattr(employee, 'shift_id') and employee.shift_id and 
            employee.job_title and employee.job_title.shift_system):
            shift = Shift.query.get(employee.shift_id)

        if not shift:
            return delay_info

        # جلب سجلات الحضور للفترة المحددة
        attendances = (Attendance.query
            .filter(
                Attendance.empId == employee.id,
                Attendance.createdAt.between(start_date, end_date)
            )
            .order_by(Attendance.createdAt, Attendance.checkInTime)
            .all())

        if not attendances:
            return delay_info

        # تجميع السجلات حسب اليوم
        daily_records = {}
        for attendance in attendances:
            try:
                if isinstance(attendance.createdAt, datetime):
                    date = attendance.createdAt.date()
                else:
                    date = attendance.createdAt

                if start_date <= date <= end_date:
                    if date not in daily_records:
                        daily_records[date] = []
                    daily_records[date].append(attendance)
            except Exception as e:
                print(f"Error processing attendance record: {str(e)}")
                continue

        # حساب التأخير والخروج المبكر لكل يوم
        total_delay_minutes = 0
        total_early_exit_minutes = 0
        delay_days = 0
        early_exit_days = 0
        violation_days = set()  # استخدام set لتجنب العد المضاعف
        
        shift_start_minutes = time_to_minutes(shift.start_time)
        shift_end_minutes = time_to_minutes(shift.end_time)
        allowed_delay_minutes = shift.allowed_delay_minutes
        allowed_exit_minutes = shift.allowed_exit_minutes

        for date, day_attendances in daily_records.items():
            try:
                # البحث عن أول دخول وآخر خروج في اليوم
                first_checkin = None
                last_checkout = None
                
                for attendance in day_attendances:
                    if attendance.checkInTime:
                        if first_checkin is None or attendance.checkInTime < first_checkin:
                            first_checkin = attendance.checkInTime
                    
                    if attendance.checkOutTime:
                        if last_checkout is None or attendance.checkOutTime > last_checkout:
                            last_checkout = attendance.checkOutTime

                # حساب دقائق التأخير
                day_delay_minutes = 0
                if first_checkin:
                    actual_checkin_minutes = time_to_minutes(first_checkin)
                    day_delay_minutes = max(0, actual_checkin_minutes - shift_start_minutes - allowed_delay_minutes)
                    
                    if day_delay_minutes > 0:
                        total_delay_minutes += day_delay_minutes
                        delay_days += 1
                        violation_days.add(date)

                # حساب دقائق الخروج المبكر
                day_early_exit_minutes = 0
                if last_checkout:
                    actual_checkout_minutes = time_to_minutes(last_checkout)
                    day_early_exit_minutes = max(0, shift_end_minutes - actual_checkout_minutes - allowed_exit_minutes)
                    
                    if day_early_exit_minutes > 0:
                        total_early_exit_minutes += day_early_exit_minutes
                        early_exit_days += 1
                        violation_days.add(date)

            except Exception as e:
                print(f"Error calculating delay/early exit for date {date}: {str(e)}")
                continue

        # حساب الإجماليات
        total_violation_minutes = total_delay_minutes + total_early_exit_minutes

        # تحديث معلومات التأخير
        delay_info.update({
            # معلومات التأخير
            'total_delay_minutes': total_delay_minutes,
            'total_delay_hours': total_delay_minutes // 60,
            'remaining_minutes': total_delay_minutes % 60,
            'total_delay_formatted': f"{total_delay_minutes // 60:02d}:{total_delay_minutes % 60:02d}",
            'delay_days': delay_days,
            
            # معلومات الخروج المبكر
            'early_exit_minutes': total_early_exit_minutes,
            'early_exit_hours': total_early_exit_minutes // 60,
            'early_exit_formatted': f"{total_early_exit_minutes // 60:02d}:{total_early_exit_minutes % 60:02d}",
            'early_exit_days': early_exit_days,
            
            # إجمالي المخالفات
            'total_violation_minutes': total_violation_minutes,
            'total_violation_hours': total_violation_minutes // 60,
            'total_violation_formatted': f"{total_violation_minutes // 60:02d}:{total_violation_minutes % 60:02d}",
            'total_violation_days': len(violation_days)
        })

        return delay_info

    except Exception as e:
        print(f"Error calculating employee delay info: {str(e)}")
        return {
            'total_delay_minutes': 0,
            'total_delay_hours': 0,
            'remaining_minutes': 0,
            'total_delay_formatted': '00:00',
            'delay_days': 0,
            'early_exit_minutes': 0,
            'early_exit_hours': 0,
            'early_exit_formatted': '00:00',
            'early_exit_days': 0,
            'total_violation_minutes': 0,
            'total_violation_hours': 0,
            'total_violation_formatted': '00:00',
            'total_violation_days': 0
        }   

# إضافة endpoint للحصول على راتب موظف واحد لفترة محددة
@payroll_bp.route('/api/payroll/employee/<int:employee_id>/period', methods=['POST'])
@token_required
def calculate_employee_period_payroll(user, employee_id):
    """
    حساب راتب موظف معين لفترة محددة مع دعم نوع الراتب
    """
    try:
        data = request.get_json()
        required_fields = ['start_date', 'end_date']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({'message': f'Missing fields: {", ".join(missing_fields)}'}), 400

        # تحديد نوع الراتب
        salary_type = data.get('salary_type', SalaryType.MONTHLY)
        if salary_type not in [SalaryType.MONTHLY, SalaryType.WEEKLY]:
            return jsonify({'message': 'Invalid salary_type. Must be "monthly" or "weekly"'}), 400

        # تحويل التواريخ
        try:
            start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'message': 'Invalid date format. Use YYYY-MM-DD'}), 400

        # التحقق من صحة الفترة
        if start_date > end_date:
            return jsonify({'message': 'Start date cannot be after end date'}), 400

        if end_date > date.today() + timedelta(days=1):
            return jsonify({'message': 'End date cannot be in the future'}), 400

        # البحث عن الموظف
        employee = Employee.query.get(employee_id)
        if not employee:
            return jsonify({'message': f'Employee with ID {employee_id} not found'}), 404

        # حساب راتب الموظف للفترة المحددة مع نوع الراتب
        salary_result = calculate_employee_salary_period(employee, start_date, end_date, salary_type)
        
        return jsonify(salary_result), 200

    except Exception as e:
        print(f"Error in calculate_employee_period_payroll: {str(e)}")
        return jsonify({'message': f'Error calculating employee payroll: {str(e)}'}), 500

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


def process_shift_day(attendances, shift, allowed_break_minutes, delay_minute_value):
    """معالجة سجلات الحضور ليوم واحد"""
    try:
        shift_start_minutes = time_to_minutes(shift.start_time)
        shift_end_minutes = time_to_minutes(shift.end_time)
        shift_duration = shift_end_minutes - shift_start_minutes
        
        working_periods = []
        total_break_minutes = 0
        first_check_in = None
        last_check_out = None

        for i, attendance in enumerate(attendances):
            if not attendance.checkInTime or not attendance.checkOutTime:
                continue

            check_in_minutes = time_to_minutes(attendance.checkInTime)
            check_out_minutes = time_to_minutes(attendance.checkOutTime)

            if first_check_in is None:
                first_check_in = check_in_minutes
            last_check_out = check_out_minutes

            period_duration = check_out_minutes - check_in_minutes
            if period_duration > 0:
                working_periods.append({
                    'start': check_in_minutes,
                    'end': check_out_minutes,
                    'duration': period_duration
                })

            if i < len(attendances) - 1 and attendances[i+1].checkInTime:
                next_check_in = time_to_minutes(attendances[i+1].checkInTime)
                break_duration = next_check_in - check_out_minutes
                if break_duration > 0:
                    total_break_minutes += break_duration

        total_working_minutes = sum(period['duration'] for period in working_periods)
        delay_minutes = max(0, first_check_in - shift_start_minutes - shift.allowed_delay_minutes)
        early_exit_minutes = max(0, shift_end_minutes - last_check_out - shift.allowed_exit_minutes) if last_check_out else 0
        overtime_minutes = max(0, total_working_minutes - shift_duration)
        excess_break_minutes = max(0, total_break_minutes - allowed_break_minutes)

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

def time_to_minutes(time_obj):
    """تحويل كائن الوقت إلى دقائق"""
    return time_obj.hour * 60 + time_obj.minute

def minutes_to_time_str(minutes):
    """تحويل الدقائق إلى نص يمثل الوقت"""
    if minutes is None:
        return None
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"

def convert_time_to_minutes(time_str):
    """تحويل نص الوقت إلى دقائق"""
    try:
        hours, minutes = map(int, time_str.split(':'))
        return hours * 60 + minutes
    except:
        return 0

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