from flask import Blueprint, render_template_string, request, jsonify
from datetime import datetime, date, timedelta
from sqlalchemy import extract, and_
from decimal import Decimal
from app import db
from app.models import AttendanceType, Employee, JobTitle, MonthlyAttendance, Attendance, ProductionMonitoring, Advance, Shift, user
from app.utils import token_required

payroll_bp = Blueprint('payroll', __name__)

@payroll_bp.route('/api/payroll/calculate-period', methods=['POST'])
@token_required
def calculate_period_payroll(user):
    """
    حساب الرواتب لفترة محددة بين تاريخين
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

        # تحويل التواريخ
        try:
            start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'message': 'Invalid date format. Use YYYY-MM-DD'}), 400

        # التحقق من صحة الفترة
        if start_date > end_date:
            return jsonify({'message': 'Start date cannot be after end date'}), 400

        if end_date > date.today():
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

        # إحصائيات عامة
        general_statistics = {
            'total_employees': len(employees),
            'total_payroll': Decimal('0'),
            'total_basic_salaries': Decimal('0'),
            'total_allowances': Decimal('0'),
            'total_additions': Decimal('0'),
            'total_deductions': Decimal('0'),
            'calculation_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'period': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'total_days': period_days
            }
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
            salary_result = calculate_employee_salary_period(employee, start_date, end_date)
            
            # تحديث الإحصائيات العامة
            general_statistics['total_basic_salaries'] += Decimal(salary_result['basic_salary'])
            general_statistics['total_allowances'] += Decimal(salary_result['allowances'])
            general_statistics['total_additions'] += Decimal(salary_result['additions'])
            general_statistics['total_deductions'] += Decimal(salary_result['deductions'])
            general_statistics['total_payroll'] += Decimal(salary_result['net_salary'])

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

def calculate_employee_salary_period(employee, start_date, end_date):
    """حساب راتب موظف واحد لفترة محددة"""
    try:
        # حساب عدد الأيام في الفترة
        period_days = (end_date - start_date).days + 1

        # القيم الأساسية
        basic_salary = Decimal(str(employee.salary or 0))
        allowances = Decimal(str(employee.allowances or 0))

        # حساب الراتب الأساسي والبدلات بشكل نسبي للفترة
        period_basic_salary = calculate_proportional_salary(basic_salary, start_date, end_date)
        period_allowances = calculate_proportional_allowances(allowances, start_date, end_date)

        # التحقق من صلاحية التأمينات للفترة
        insurance_deduction = calculate_insurance_for_period(employee, start_date, end_date)

        total_additions = Decimal('0')
        total_deductions = insurance_deduction
        notes = []
        system_details = {}
        system_type = 'none'

        # إضافة ملاحظة حول التأمينات
        if insurance_deduction > 0:
            notes.append(f"التأمينات للفترة: {insurance_deduction}")

        # === الإضافات والخصومات الديناميكية (بدلات/خصومات مخصصة لكل موظف) ===
        # تُحسب نسبياً لفترة الحساب بنفس منطق الراتب والبدلات
        dynamic_components = []
        try:
            components = list(employee.salary_components.filter_by(is_active=True))
        except Exception:
            components = []
        for comp in components:
            amount = Decimal(str(comp.amount or 0))
            proportional = calculate_proportional_salary(amount, start_date, end_date)
            comp_info = {
                'id': comp.id,
                'name': comp.name,
                'type': comp.component_type,
                'monthly_amount': str(amount),
                'period_amount': str(proportional),
            }
            if comp.component_type == 'addition':
                total_additions += proportional
            elif comp.component_type == 'deduction':
                total_deductions += proportional
            dynamic_components.append(comp_info)

        if dynamic_components:
            names = [f"{c['name']}({c['type'][:3]}):{c['period_amount']}" for c in dynamic_components]
            notes.append("مكونات ديناميكية: " + ", ".join(names))

        # التحقق من نوع الموظف وحساب الراتب حسب النظام
        if employee.profession and not employee.job_title:
            # موظف بنظام الساعات
            hourly_result = calculate_hourly_system_period(employee, start_date, end_date)
            total_additions += Decimal(str(hourly_result.get('additions', '0')))
            total_deductions += Decimal(str(hourly_result.get('deductions', '0')))
            system_details = hourly_result.get('details', {})
            system_type = 'hourly'
            notes.append(hourly_result.get('notes', ''))
        elif employee.job_title:
            # موظف بمسمى وظيفي - حساب حسب نوع النظام
            if employee.job_title.month_system:
                monthly_result = calculate_monthly_system_period(employee, start_date, end_date)
                total_additions += Decimal(str(monthly_result.get('additions', '0')))
                total_deductions += Decimal(str(monthly_result.get('deductions', '0')))
                system_details = monthly_result.get('details', {})
                system_type = 'monthly'
                notes.append(monthly_result.get('notes', ''))
            elif employee.job_title.production_system:
                production_result = calculate_production_system_period(employee, start_date, end_date)
                total_additions += Decimal(str(production_result.get('additions', '0')))
                system_details = production_result.get('details', {})
                system_type = 'production'
                notes.append(production_result.get('notes', ''))
            elif employee.job_title.shift_system:
                shift_result = calculate_shift_system_period(employee, start_date, end_date)
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
            'dynamic_components': dynamic_components,
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
            f"خطأ في حساب الراتب: {str(e)}", start_date, end_date
        )

def calculate_proportional_salary(monthly_salary, start_date, end_date):
    """حساب الراتب الأساسي بشكل نسبي للفترة المحددة"""
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
        print(f"Error calculating proportional salary: {str(e)}")
        return monthly_salary

def calculate_proportional_allowances(allowances, start_date, end_date):
    """حساب البدلات بشكل نسبي للفترة المحددة"""
    return calculate_proportional_salary(allowances, start_date, end_date)

def calculate_insurance_for_period(employee, start_date, end_date):
    """حساب التأمينات للفترة المحددة"""
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
        
        # حساب الأيام الفعلية للتأمين في الفترة
        insurance_days = (insurance_end - insurance_start).days + 1
        total_period_days = (end_date - start_date).days + 1
        
        # حساب التأمين بشكل نسبي
        insurance_proportion = Decimal(str(insurance_days)) / Decimal(str(total_period_days))
        monthly_insurance = Decimal(str(employee.insurance_deduction))
        
        return calculate_proportional_salary(monthly_insurance, insurance_start, insurance_end)
        
    except Exception as e:
        print(f"Error calculating insurance for period: {str(e)}")
        return Decimal('0')

def calculate_monthly_system_period(employee, start_date, end_date):
    """حساب راتب النظام الشهري لفترة محددة"""
    try:
        attendances = MonthlyAttendance.query.filter(
            MonthlyAttendance.employee_id == employee.id,
            MonthlyAttendance.date.between(start_date, end_date)
        ).all()

        # حساب المعدل اليومي بناءً على الراتب الشهري
        monthly_salary = Decimal(str(employee.salary or 0))
        period_days = (end_date - start_date).days + 1
        
        # حساب المعدل اليومي (استخدام 30 كمعيار أو الأيام الفعلية في الشهر)
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
            'daily_rate': str(daily_rate),
            'period_days': period_days
        }

        # معالجة سجلات الحضور
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

        # حساب الأيام المفقودة (الأيام التي ليس لها سجل حضور)
        total_expected_days = period_days
        total_recorded_days = len(recorded_dates)
        missing_days = max(0, total_expected_days - total_recorded_days)
        
        if missing_days > 0:
            # اعتبار الأيام المفقودة كغياب بدون عذر
            deductions += (daily_rate * Decimal('2') * Decimal(str(missing_days)))
            attendance_details['missing_days'] = missing_days
            attendance_details['unexcused_absences'] += missing_days

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

def calculate_production_system_period(employee, start_date, end_date):
    """حساب راتب نظام الإنتاج لفترة محددة"""
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
            f"الفترة: {period_days} يوم | "
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


def calculate_shift_system_period(employee, start_date, end_date):
    """حساب راتب نظام الورديات لفترة محددة مع دعم الإجازات المعتمدة"""
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
                Attendance.checkInTime.isnot(None),
                Attendance.createdAt.between(start_date, end_date)
            )
            .order_by(Attendance.createdAt, Attendance.checkInTime)
            .all())

        # جلب الإجازات المعتمدة للفترة المحددة
        from app.models.leave import Leave
        approved_leaves = Leave.get_employee_leaves_for_period(employee.id, start_date, end_date)

        # إنشاء مصفوفة الإجازات مفهرسة بالتاريخ
        leaves_dict = {}
        for leave in approved_leaves:
            current_date = leave.start_date
            end_leave_date = leave.end_date or leave.start_date
            
            while current_date <= end_leave_date and current_date <= end_date:
                if current_date >= start_date:
                    if current_date not in leaves_dict:
                        leaves_dict[current_date] = []
                    leaves_dict[current_date].append(leave)
                current_date += timedelta(days=1)

        # جلب إعدادات المسمى الوظيفي
        job_title = employee.job_title
        allowed_break_minutes = convert_time_to_minutes(job_title.allowed_break_time or "00:00")
        overtime_hour_value = Decimal(str(job_title.overtime_hour_value or 0))
        delay_minute_value = Decimal(str(job_title.delay_minute_value or 0))

        # حساب القيمة اليومية للموظف
        if hasattr(employee, 'daily_rate') and employee.daily_rate:
            daily_rate = Decimal(str(employee.daily_rate))
        else:
            monthly_salary = Decimal(str(employee.salary or 0))
            daily_rate = monthly_salary / Decimal('30')

        # تجميع السجلات حسب اليوم
        daily_records = {}
        for attendance in attendances:
            try:
                if attendance.checkInTime:
                    if isinstance(attendance.checkInTime, datetime):
                        date = attendance.checkInTime.date()
                    else:
                        continue

                    if start_date <= date <= end_date:
                        if date not in daily_records:
                            daily_records[date] = []
                        daily_records[date].append(attendance)
            except Exception as e:
                print(f"Error processing attendance record: {str(e)}")
                continue

        # متغيرات لتجميع النتائج
        total_working_minutes = 0
        total_overtime_minutes = 0
        total_delay_minutes = 0
        total_excess_break_minutes = 0
        total_approved_leave_value = Decimal('0')  # قيمة الإجازات المعتمدة
        period_details = []
        leave_summary = []

        # معالجة كل يوم على حدة
        current_date = start_date
        while current_date <= end_date:
            try:
                day_name = get_day_name_english(current_date)
                
                # التحقق من كونه يوم عمل في الوردية
                if not shift.is_working_day(day_name):
                    period_details.append({
                        'date': current_date.strftime('%Y-%m-%d'),
                        'day_name': day_name,
                        'is_working_day': False,
                        'working_minutes': 0,
                        'overtime_minutes': 0,
                        'delay_minutes': 0,
                        'break_minutes': 0,
                        'excess_break_minutes': 0,
                        'notes': 'يوم غير عمل حسب الوردية'
                    })
                    current_date += timedelta(days=1)
                    continue

                # الحصول على أوقات العمل لهذا اليوم
                day_start_time, day_end_time = shift.get_day_times(day_name)
                
                if not day_start_time or not day_end_time:
                    period_details.append({
                        'date': current_date.strftime('%Y-%m-%d'),
                        'day_name': day_name,
                        'is_working_day': True,
                        'working_minutes': 0,
                        'overtime_minutes': 0,
                        'delay_minutes': 0,
                        'break_minutes': 0,
                        'excess_break_minutes': 0,
                        'notes': 'أوقات العمل غير محددة لهذا اليوم'
                    })
                    current_date += timedelta(days=1)
                    continue

                # التحقق من وجود إجازة معتمدة لهذا اليوم
                day_leaves = leaves_dict.get(current_date, [])
                day_leave_hours = 0
                leave_notes = []
                
                for leave in day_leaves:
                    if leave.leave_type == 'daily_leave':
                        # إجازة يومية - احسب قيمة اليوم كاملاً
                        total_approved_leave_value += daily_rate
                        leave_notes.append(f'إجازة يومية معتمدة - معاملة {leave.transaction_id}')
                        leave_summary.append({
                            'date': current_date.strftime('%Y-%m-%d'),
                            'leave_type': 'daily_leave',
                            'transaction_id': leave.transaction_id,
                            'value': str(daily_rate),
                            'reason': leave.reason
                        })
                    elif leave.leave_type == 'hourly_leave':
                        # إجازة ساعية - احسب قيمة الساعات
                        leave_hours = leave.hours or 0
                        hourly_rate = daily_rate / Decimal('8')  # افتراض 8 ساعات عمل يومياً
                        leave_value = hourly_rate * Decimal(str(leave_hours))
                        total_approved_leave_value += leave_value
                        day_leave_hours += leave_hours
                        leave_notes.append(f'إجازة ساعية {leave_hours} ساعة - معاملة {leave.transaction_id}')
                        leave_summary.append({
                            'date': current_date.strftime('%Y-%m-%d'),
                            'leave_type': 'hourly_leave',
                            'hours': leave_hours,
                            'transaction_id': leave.transaction_id,
                            'value': str(leave_value),
                            'reason': leave.reason
                        })

                # معالجة سجلات الحضور لهذا اليوم
                day_attendances = daily_records.get(current_date, [])
                
                if day_attendances:
                    # حساب الحضور مع مراعاة الإجازات الساعية
                    day_result = process_shift_day_with_approved_leaves(
                        day_attendances,
                        day_start_time,
                        day_end_time,
                        shift.allowed_delay_minutes,
                        shift.allowed_exit_minutes,
                        allowed_break_minutes,
                        day_leave_hours
                    )
                    
                    total_working_minutes += day_result['working_minutes']
                    total_overtime_minutes += day_result['overtime_minutes']
                    total_delay_minutes += day_result['delay_minutes']
                    total_excess_break_minutes += day_result['excess_break_minutes']
                    
                    period_details.append({
                        'date': current_date.strftime('%Y-%m-%d'),
                        'day_name': day_name,
                        'is_working_day': True,
                        'scheduled_start': day_start_time.strftime('%H:%M'),
                        'scheduled_end': day_end_time.strftime('%H:%M'),
                        'approved_leave_hours': day_leave_hours,
                        'leave_notes': leave_notes,
                        **day_result
                    })
                else:
                    # لا توجد سجلات حضور
                    if day_leaves:
                        # يوجد إجازة معتمدة - لا يتم خصم شيء
                        period_details.append({
                            'date': current_date.strftime('%Y-%m-%d'),
                            'day_name': day_name,
                            'is_working_day': True,
                            'scheduled_start': day_start_time.strftime('%H:%M'),
                            'scheduled_end': day_end_time.strftime('%H:%M'),
                            'working_minutes': 0,
                            'overtime_minutes': 0,
                            'delay_minutes': 0,
                            'break_minutes': 0,
                            'excess_break_minutes': 0,
                            'approved_leave_hours': day_leave_hours,
                            'leave_notes': leave_notes,
                            'notes': f'إجازة معتمدة - {", ".join(leave_notes)}'
                        })
                    else:
                        # غياب بدون إجازة معتمدة - لا يتم خصم شيء حسب النظام الحالي
                        period_details.append({
                            'date': current_date.strftime('%Y-%m-%d'),
                            'day_name': day_name,
                            'is_working_day': True,
                            'scheduled_start': day_start_time.strftime('%H:%M'),
                            'scheduled_end': day_end_time.strftime('%H:%M'),
                            'working_minutes': 0,
                            'overtime_minutes': 0,
                            'delay_minutes': 0,
                            'break_minutes': 0,
                            'excess_break_minutes': 0,
                            'notes': 'غياب بدون إجازة معتمدة - لا يوجد خصم'
                        })

            except Exception as e:
                print(f"Error processing day {current_date}: {str(e)}")
                
            current_date += timedelta(days=1)

        # حساب القيم المالية
        overtime_value = (Decimal(str(total_overtime_minutes)) / Decimal('60')) * overtime_hour_value
        delay_deductions = Decimal(str(total_delay_minutes)) * delay_minute_value
        break_deductions = Decimal(str(total_excess_break_minutes)) * delay_minute_value
        
        # إجمالي الإضافات = الإضافي + قيمة الإجازات المعتمدة
        total_additions = overtime_value + total_approved_leave_value
        total_deductions = delay_deductions + break_deductions

        period_days = (end_date - start_date).days + 1
        working_days_count = len([d for d in period_details if d.get('is_working_day', False)])
        
        details = {
            'period_info': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'total_days': period_days,
                'working_days': working_days_count
            },
            'total_working_minutes': total_working_minutes,
            'total_overtime_minutes': total_overtime_minutes,
            'total_delay_minutes': total_delay_minutes,
            'total_excess_break_minutes': total_excess_break_minutes,
            'overtime_value': str(overtime_value),
            'delay_deductions': str(delay_deductions),
            'break_deductions': str(break_deductions),
            'approved_leave_value': str(total_approved_leave_value),
            'daily_rate': str(daily_rate),
            'daily_records': period_details,
            'leave_summary': leave_summary,
            'shift_info': {
                'shift_name': shift.name,
                'allowed_delay_minutes': shift.allowed_delay_minutes,
                'allowed_exit_minutes': shift.allowed_exit_minutes,
                'allowed_break_minutes': allowed_break_minutes,
                'daily_schedule': shift.daily_schedule
            }
        }

        return {
            'additions': total_additions,
            'deductions': total_deductions,
            'details': details,
            'notes': (
                f"الفترة: {period_days} يوم | "
                f"أيام العمل: {working_days_count}, "
                f"ساعات العمل: {total_working_minutes // 60}, "
                f"ساعات إضافي: {total_overtime_minutes // 60}, "
                f"دقائق تأخير: {total_delay_minutes}, "
                f"دقائق استراحة زائدة: {total_excess_break_minutes}, "
                f"قيمة الإجازات المعتمدة: {total_approved_leave_value}"
            )
        }

    except Exception as e:
        print(f"Error in shift period calculation: {str(e)}")
        raise Exception(f"Error in shift system period calculation: {str(e)}")

def process_shift_day_with_approved_leaves(attendances, day_start_time, day_end_time, 
                                         allowed_delay_minutes, allowed_exit_minutes, 
                                         allowed_break_minutes, approved_leave_hours):
    """معالجة سجلات الحضور ليوم واحد مع مراعاة الإجازات الساعية المعتمدة"""
    try:
        day_start_minutes = time_to_minutes(day_start_time)
        day_end_minutes = time_to_minutes(day_end_time)
        day_duration = day_end_minutes - day_start_minutes
        
        # تحويل ساعات الإجازة المعتمدة إلى دقائق
        approved_leave_minutes = approved_leave_hours * 60
        
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

            # حساب فترات الاستراحة
            if i < len(attendances) - 1 and attendances[i+1].checkInTime:
                next_check_in = time_to_minutes(attendances[i+1].checkInTime)
                break_duration = next_check_in - check_out_minutes
                if break_duration > 0:
                    total_break_minutes += break_duration

        total_working_minutes = sum(period['duration'] for period in working_periods)
        
        # إضافة دقائق الإجازة المعتمدة لإجمالي العمل
        effective_working_minutes = total_working_minutes + approved_leave_minutes
        
        # حساب التأخير (مع مراعاة الإجازات المعتمدة)
        delay_minutes = max(0, first_check_in - day_start_minutes - allowed_delay_minutes) if first_check_in else 0
        
        # حساب الخروج المبكر
        early_exit_minutes = max(0, day_end_minutes - last_check_out - allowed_exit_minutes) if last_check_out else 0
        
        # حساب الساعات الإضافية (بناءً على العمل الفعلي + الإجازة المعتمدة)
        overtime_minutes = max(0, effective_working_minutes - day_duration)
        
        # حساب الاستراحة الزائدة
        excess_break_minutes = max(0, total_break_minutes - allowed_break_minutes)

        return {
            'working_minutes': total_working_minutes,
            'effective_working_minutes': effective_working_minutes,
            'approved_leave_minutes': approved_leave_minutes,
            'overtime_minutes': overtime_minutes,
            'delay_minutes': delay_minutes + early_exit_minutes,
            'break_minutes': total_break_minutes,
            'excess_break_minutes': excess_break_minutes,
            'periods': working_periods,
            'first_check_in': minutes_to_time_str(first_check_in),
            'last_check_out': minutes_to_time_str(last_check_out),
            'notes': f'يوم عمل - عمل فعلي: {total_working_minutes} دقيقة + إجازة معتمدة: {approved_leave_minutes} دقيقة'
        }

    except Exception as e:
        print(f"Error processing shift day with approved leaves: {str(e)}")
        raise

def process_shift_day_with_schedule(attendances, day_start_time, day_end_time, 
                                   allowed_delay_minutes, allowed_exit_minutes, allowed_break_minutes):
    """معالجة سجلات الحضور ليوم واحد مع جدولة محددة لذلك اليوم"""
    try:
        day_start_minutes = time_to_minutes(day_start_time)
        day_end_minutes = time_to_minutes(day_end_time)
        day_duration = day_end_minutes - day_start_minutes
        
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

            # حساب فترات الاستراحة
            if i < len(attendances) - 1 and attendances[i+1].checkInTime:
                next_check_in = time_to_minutes(attendances[i+1].checkInTime)
                break_duration = next_check_in - check_out_minutes
                if break_duration > 0:
                    total_break_minutes += break_duration

        total_working_minutes = sum(period['duration'] for period in working_periods)
        
        # حساب التأخير بناء على وقت الدخول المحدد لهذا اليوم
        delay_minutes = max(0, first_check_in - day_start_minutes - allowed_delay_minutes) if first_check_in else 0
        
        # حساب الخروج المبكر بناء على وقت الخروج المحدد لهذا اليوم
        early_exit_minutes = max(0, day_end_minutes - last_check_out - allowed_exit_minutes) if last_check_out else 0
        
        # حساب الساعات الإضافية
        overtime_minutes = max(0, total_working_minutes - day_duration)
        
        # حساب الاستراحة الزائدة
        excess_break_minutes = max(0, total_break_minutes - allowed_break_minutes)

        return {
            'working_minutes': total_working_minutes,
            'overtime_minutes': overtime_minutes,
            'delay_minutes': delay_minutes + early_exit_minutes,
            'break_minutes': total_break_minutes,
            'excess_break_minutes': excess_break_minutes,
            'periods': working_periods,
            'first_check_in': minutes_to_time_str(first_check_in),
            'last_check_out': minutes_to_time_str(last_check_out),
            'notes': f'يوم عمل عادي - مجموع العمل: {total_working_minutes} دقيقة'
        }

    except Exception as e:
        print(f"Error processing shift day with schedule: {str(e)}")
        raise


def get_day_name_english(date):
    """الحصول على اسم اليوم بالإنجليزية"""
    days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    return days[date.weekday()]


def calculate_day_duration_minutes(start_time, end_time):
    """حساب مدة اليوم بالدقائق"""
    start_minutes = time_to_minutes(start_time)
    end_minutes = time_to_minutes(end_time)
    return end_minutes - start_minutes


def calculate_hourly_system_period(employee, start_date, end_date):
    """حساب راتب نظام الساعات لفترة محددة"""
    try:
        # التحقق من وجود المهنة
        if not employee.profession:
            return {
                'additions': Decimal('0'),
                'deductions': Decimal('0'),
                'details': {},
                'notes': "لا توجد مهنة محددة للموظف"
            }

        # جلب سجلات الحضور للفترة المحددة حسب checkInTime
        attendances = (Attendance.query
            .filter(
                Attendance.empId == employee.id,
                Attendance.checkInTime.isnot(None),
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

        # تجميع السجلات حسب اليوم بناءً على checkInTime
        daily_records = {}
        for attendance in attendances:
            try:
                # استخراج التاريخ من checkInTime
                if attendance.checkInTime:
                    if isinstance(attendance.checkInTime, datetime):
                        date = attendance.checkInTime.date()
                    else:
                        continue

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
                f"الفترة: {period_days} يوم | "
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
    """حساب السلف للفترة المحددة"""
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

def create_basic_result_period(employee, basic_salary, allowances, additions, deductions, notes, start_date, end_date):
    """إنشاء نتيجة أساسية للراتب للفترة المحددة"""
    net_salary = basic_salary + allowances + additions - deductions
    period_days = (end_date - start_date).days + 1
    
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
        'calculation_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'period_info': {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'total_days': period_days
        }
    }

# إضافة endpoint للحصول على راتب موظف واحد لفترة محددة
@payroll_bp.route('/api/payroll/employee/<int:employee_id>/period', methods=['POST'])
@token_required
def calculate_employee_period_payroll(user, employee_id):
    """
    حساب راتب موظف معين لفترة محددة
    """
    try:
        data = request.get_json()
        required_fields = ['start_date', 'end_date']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({'message': f'Missing fields: {", ".join(missing_fields)}'}), 400

        # تحويل التواريخ
        try:
            start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'message': 'Invalid date format. Use YYYY-MM-DD'}), 400

        # التحقق من صحة الفترة
        if start_date > end_date:
            return jsonify({'message': 'Start date cannot be after end date'}), 400

        if end_date > date.today():
            return jsonify({'message': 'End date cannot be in the future'}), 400

        # البحث عن الموظف
        employee = Employee.query.get(employee_id)
        if not employee:
            return jsonify({'message': f'Employee with ID {employee_id} not found'}), 404

        # حساب راتب الموظف للفترة المحددة
        salary_result = calculate_employee_salary_period(employee, start_date, end_date)
        
        return jsonify(salary_result), 200

    except Exception as e:
        print(f"Error in calculate_employee_period_payroll: {str(e)}")
        return jsonify({'message': f'Error calculating employee payroll: {str(e)}'}), 500

# دوال مساعدة (نفس الدوال الموجودة في الكود الأصلي)
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
    """تحديث إحصائيات نظام الورديات مع إضافة خصومات الغياب"""
    stats['total_salaries'] += Decimal(salary_result['net_salary'])
    
    if 'system_details' in salary_result:
        shift = salary_result['system_details']
        stats['total_working_hours'] += shift.get('total_working_minutes', 0) // 60
        stats['total_overtime_hours'] += shift.get('total_overtime_minutes', 0) // 60
        stats['total_delay_minutes'] += shift.get('total_delay_minutes', 0)
        stats['total_break_minutes'] += shift.get('total_excess_break_minutes', 0)
        
        # إضافة إحصائيات خصومات الغياب
        if 'absence_deductions' not in stats:
            stats['total_absence_deductions'] = Decimal('0')
            stats['absence_transactions_count'] = 0
        
        stats['total_absence_deductions'] += Decimal(str(shift.get('absence_deductions', '0')))
        stats['absence_transactions_count'] += len(shift.get('absence_transactions', []))

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
    """معالجة سجلات الحضور ليوم واحد (نفس الدالة الأصلية)"""
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
    



# ==================== HTML Templates ====================

PAYSLIP_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>وصل الراتب - {{ employee_name }}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        @page {
            size: A4;
            margin: 10mm;
        }

        @media print {
            body {
                margin: 0;
                padding: 0;
            }
            
            .payslip-container {
                page-break-inside: avoid;
                margin: 0;
                padding: 0;
            }

            .no-print {
                display: none !important;
            }

            a {
                color: inherit;
                text-decoration: none;
            }
        }

        body {
            font-family: 'Arial', 'Segoe UI', sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f5f5f5;
            padding: 20px;
        }

        .payslip-container {
            background-color: white;
            max-width: 21cm;
            height: 29.7cm;
            margin: 0 auto;
            padding: 20mm;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }

        /* ========== Header ========== */
        .payslip-header {
            text-align: center;
            border-bottom: 3px solid #1f4788;
            padding-bottom: 15px;
            margin-bottom: 20px;
        }

        .company-name {
            font-size: 18px;
            font-weight: bold;
            color: #1f4788;
            margin-bottom: 5px;
        }

        .payslip-title {
            font-size: 16px;
            font-weight: bold;
            color: #34568B;
            margin-bottom: 10px;
        }

        .company-details {
            font-size: 9px;
            color: #666;
        }

        /* ========== Employee Info ========== */
        .employee-info {
            background-color: #f0f4f8;
            border: 1px solid #d0d0d0;
            padding: 12px;
            margin-bottom: 15px;
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 10px;
            font-size: 10px;
        }

        .info-item {
            text-align: right;
        }

        .info-label {
            font-weight: bold;
            color: #1f4788;
            display: inline;
        }

        .info-value {
            color: #333;
            display: inline;
        }

        /* ========== Salary Details Table ========== */
        .salary-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 15px;
            font-size: 10px;
        }

        .salary-table th {
            background-color: #1f4788;
            color: white;
            padding: 10px;
            text-align: right;
            font-weight: bold;
            border: 1px solid #1f4788;
        }

        .salary-table td {
            padding: 8px 10px;
            text-align: right;
            border: 1px solid #d0d0d0;
        }

        .salary-table tr:nth-child(even) {
            background-color: #f9f9f9;
        }

        .salary-table tr:hover {
            background-color: #f0f4f8;
        }

        .table-section-header {
            background-color: #34568B;
            color: white;
            font-weight: bold;
        }

        .total-row {
            background-color: #27ae60 !important;
            color: white;
            font-weight: bold;
            font-size: 11px;
        }

        .total-row td {
            border-color: #27ae60;
        }

        .separator-row {
            background-color: white !important;
            border-top: 2px solid #1f4788;
            border-bottom: 2px solid #1f4788;
        }

        .separator-row td {
            background-color: white !important;
            border: none;
            padding: 3px;
        }

        /* ========== Breakdown Details ========== */
        .breakdown-section {
            margin-bottom: 12px;
        }

        .breakdown-title {
            font-size: 10px;
            font-weight: bold;
            color: #34568B;
            margin-bottom: 6px;
            padding-bottom: 3px;
            border-bottom: 1px solid #d0d0d0;
        }

        .breakdown-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 9px;
        }

        .breakdown-table td {
            padding: 4px 8px;
            text-align: right;
            border: 1px solid #e0e0e0;
        }

        .breakdown-table tr:nth-child(even) {
            background-color: #fafafa;
        }

        .breakdown-label {
            background-color: #f0f4f8;
            font-weight: bold;
            width: 70%;
        }

        .breakdown-value {
            background-color: white;
            text-align: center;
            width: 30%;
        }

        /* ========== Notes ========== */
        .notes-section {
            background-color: #fff8dc;
            border-left: 3px solid #ffa500;
            padding: 8px;
            margin-bottom: 12px;
            font-size: 9px;
            color: #666;
            text-align: right;
        }

        .notes-section strong {
            color: #333;
            display: block;
            margin-bottom: 3px;
        }

        /* ========== Signatures ========== */
        .signatures-section {
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #d0d0d0;
        }

        .signatures-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 9px;
        }

        .signatures-table td {
            padding: 20px 10px 5px 10px;
            text-align: center;
            border: none;
        }

        .signature-line {
            border-top: 1px solid #000;
            padding-top: 3px;
        }

        .signature-label {
            font-weight: bold;
            font-size: 9px;
        }

        /* ========== Footer ========== */
        .payslip-footer {
            text-align: center;
            font-size: 8px;
            color: #999;
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px dotted #d0d0d0;
        }

        /* ========== Print Controls ========== */
        .print-controls {
            no-print: true;
            text-align: center;
            margin-bottom: 20px;
            display: flex;
            gap: 10px;
            justify-content: center;
            flex-wrap: wrap;
        }

        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            font-weight: bold;
            transition: all 0.3s ease;
        }

        .btn-print {
            background-color: #27ae60;
            color: white;
        }

        .btn-print:hover {
            background-color: #229954;
        }

        .btn-download {
            background-color: #3498db;
            color: white;
        }

        .btn-download:hover {
            background-color: #2980b9;
        }

        .btn-close {
            background-color: #e74c3c;
            color: white;
        }

        .btn-close:hover {
            background-color: #c0392b;
        }

        /* ========== Responsive ========== */
        @media screen and (max-width: 768px) {
            .employee-info {
                grid-template-columns: 1fr;
            }

            .salary-table th,
            .salary-table td {
                padding: 6px;
                font-size: 9px;
            }

            .payslip-container {
                padding: 15mm;
                height: auto;
            }
        }

        /* ========== Page Break ========== */
        .page-break {
            page-break-after: always;
        }

        /* ========== Status Badge ========== */
        .status-badge {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 9px;
            font-weight: bold;
            margin-left: 5px;
        }

        .status-success {
            background-color: #d4edda;
            color: #155724;
        }

        .status-warning {
            background-color: #fff3cd;
            color: #856404;
        }

        .status-error {
            background-color: #f8d7da;
            color: #721c24;
        }
    </style>
</head>
<body>
    <!-- Print Controls -->
    <div class="print-controls no-print">
        <button class="btn btn-print" onclick="window.print()">
            🖨️ طباعة
        </button>
        <button class="btn btn-download" onclick="downloadHTML()">
            ⬇️ تحميل HTML
        </button>
        <button class="btn btn-close" onclick="window.close()">
            ✕ إغلاق
        </button>
    </div>

    <!-- Payslip Container -->
    <div class="payslip-container">
        <!-- Header -->
        <div class="payslip-header">
            <div class="company-name">شركتنا للخدمات</div>
            <div class="company-details">
                العنوان: مصر | الهاتف: 0500000000 | الرقم الضريبي: 123456789
            </div>
            <div class="payslip-title">وصل الراتب الشهري</div>
        </div>

        <!-- Employee Information -->
        <div class="employee-info">
            <div class="info-item">
                <span class="info-label">الاسم:</span>
                <span class="info-value">{{ employee_name }}</span>
            </div>
            <div class="info-item">
                <span class="info-label">رقم الموظف:</span>
                <span class="info-value">{{ employee_id }}</span>
            </div>
            <div class="info-item">
                <span class="info-label">البصمة:</span>
                <span class="info-value">{{ fingerprint_id }}</span>
            </div>
            <div class="info-item">
                <span class="info-label">المنصب:</span>
                <span class="info-value">{{ position }}</span>
            </div>
            <div class="info-item">
                <span class="info-label">نظام العمل:</span>
                <span class="info-value">{{ system_type }}</span>
            </div>
            <div class="info-item">
                <span class="info-label">الفترة:</span>
                <span class="info-value">{{ period_start }} إلى {{ period_end }} ({{ period_days }} يوم)</span>
            </div>
        </div>

        <!-- Salary Details Table -->
        <table class="salary-table">
            <thead>
                <tr>
                    <th>البند</th>
                    <th>المبلغ (ل.س)</th>
                    <th>ملاحظات</th>
                </tr>
            </thead>
            <tbody>
                {% if basic_salary > 0 %}
                <tr>
                    <td>الراتب الأساسي</td>
                    <td>{{ "%.2f"|format(basic_salary) }}</td>
                    <td>أساسي</td>
                </tr>
                {% endif %}

                {% if allowances > 0 %}
                <tr>
                    <td>البدلات</td>
                    <td>{{ "%.2f"|format(allowances) }}</td>
                    <td>إضافات شهرية</td>
                </tr>
                {% endif %}

                {% if additions > 0 %}
                <tr>
                    <td>الإضافات</td>
                    <td>{{ "%.2f"|format(additions) }}</td>
                    <td>من نظام {{ system_type }}</td>
                </tr>
                {% endif %}

                {% if deductions > 0 %}
                <tr>
                    <td>الخصومات</td>
                    <td>-{{ "%.2f"|format(deductions) }}</td>
                    <td>تأمين وسلف</td>
                </tr>
                {% endif %}

                <tr class="separator-row">
                    <td colspan="3"></td>
                </tr>

                <tr class="total-row">
                    <td>الراتب الصافي</td>
                    <td>{{ "%.2f"|format(net_salary) }}</td>
                    <td>المبلغ المستحق</td>
                </tr>
            </tbody>
        </table>

        <!-- Breakdown Details -->
        {% if system_details %}
        <div class="breakdown-section">
            <div class="breakdown-title">{{ breakdown_title }}</div>
            <table class="breakdown-table">
                {% for key, value in breakdown_details.items() %}
                <tr>
                    <td class="breakdown-label">{{ key }}</td>
                    <td class="breakdown-value">{{ value }}</td>
                </tr>
                {% endfor %}
            </table>
        </div>
        {% endif %}

        <!-- Notes -->
        {% if notes %}
        <div class="notes-section">
            <strong>ملاحظات:</strong>
            {{ notes }}
        </div>
        {% endif %}

        <!-- Signatures -->
        <div class="signatures-section">
            <table class="signatures-table">
                <tr>
                    <td style="width: 33%">توقيع الموظف</td>
                    <td style="width: 33%">توقيع المدير</td>
                    <td style="width: 33%">توقيع الحسابات</td>
                </tr>
                <tr>
                    <td class="signature-line">__________________</td>
                    <td class="signature-line">__________________</td>
                    <td class="signature-line">__________________</td>
                </tr>
                <tr>
                    <td>{{ current_date }}</td>
                    <td></td>
                    <td></td>
                </tr>
            </table>
        </div>

        <!-- Footer -->
        <div class="payslip-footer">
            <p>هذا الوصل يثبت استلام الراتب. يرجى مراجعة الحسابات والتأكد من صحة البيانات</p>
            <p>{{ generated_at }}</p>
        </div>
    </div>

    <script>
        function downloadHTML() {
            const element = document.querySelector('.payslip-container');
            const html = `
                <!DOCTYPE html>
                <html lang="ar" dir="rtl">
                <head>
                    <meta charset="UTF-8">
                    <title>وصل الراتب - {{ employee_name }}</title>
                    <style>
                        ${document.querySelector('style').textContent}
                    </style>
                </head>
                <body>
                    ${element.outerHTML}
                </body>
                </html>
            `;
            
            const blob = new Blob([html], { type: 'text/html' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'payslip_{{ employee_id }}_{{ period_start }}.html';
            a.click();
            window.URL.revokeObjectURL(url);
        }
    </script>
</body>
</html>
"""

# ==================== Helper Functions ====================

def format_currency(value):
    """تنسيق القيمة كعملة"""
    try:
        val = float(value)
        return f"{val:,.2f}"
    except:
        return str(value)

def get_system_type_display(system_type):
    """الحصول على اسم نظام العمل للعرض"""
    system_map = {
        'monthly': 'نظام شهري',
        'production': 'نظام إنتاج',
        'shift': 'نظام ورديات',
        'hourly': 'نظام ساعي',
        'none': 'غير محدد'
    }
    return system_map.get(system_type, system_type)

def get_breakdown_details(salary_result, system_type):
    """الحصول على تفاصيل النظام للعرض"""
    details = {}
    system_details = salary_result.get('system_details', {})
    
    if system_type == 'monthly' and system_details:
        details = {
            'أيام كاملة': str(system_details.get('full_days', 0)),
            'أنصاف أيام': str(system_details.get('half_days', 0)),
            'أيام أونلاين': str(system_details.get('online_days', 0)),
            'غياب بعذر': str(system_details.get('excused_absences', 0)),
            'غياب بدون عذر': str(system_details.get('unexcused_absences', 0)),
        }
    
    elif system_type == 'production' and system_details:
        details = {
            'إجمالي القطع': str(system_details.get('total_pieces', 0)),
            'إجمالي القيمة': format_currency(system_details.get('total_value', 0)),
        }
        quality = system_details.get('quality_summary', {})
        for grade in ['A', 'B', 'C', 'D', 'E']:
            if grade in quality and quality[grade]['count'] > 0:
                details[f"جودة {grade}"] = f"{quality[grade]['count']} قطعة"
    
    elif system_type == 'shift' and system_details:
        details = {
            'ساعات العمل': f"{system_details.get('total_working_minutes', 0) // 60} ساعة",
            'ساعات إضافية': f"{system_details.get('total_overtime_minutes', 0) // 60} ساعة",
            'دقائق التأخير': str(system_details.get('total_delay_minutes', 0)),
            'قيمة الإضافي': format_currency(system_details.get('overtime_value', 0)),
        }
        if system_details.get('approved_leave_value'):
            details['قيمة الإجازات'] = format_currency(system_details.get('approved_leave_value', 0))
    
    elif system_type == 'hourly' and system_details:
        details = {
            'إجمالي الساعات': system_details.get('total_hours', '0'),
            'معدل الساعة': format_currency(system_details.get('hourly_rate', 0)),
            'أجر اليوم': format_currency(system_details.get('daily_rate', 0)),
        }
    
    return details

# ==================== API Routes ====================

@payroll_bp.route('/api/reports/payslip/<int:employee_id>/period', methods=['POST'])
@token_required
def generate_payslip_html(user, employee_id):
    """
    إنشاء وصل راتب HTML قابل للطباعة
    
    URL: POST /api/payslip/2/period
    
    البيانات المطلوبة:
    {
        "start_date": "2024-12-01",
        "end_date": "2024-12-31"
    }
    
    الرد: صفحة HTML
    """
    try:
        data = request.get_json()
        
        # التحقق من البيانات المطلوبة
        if not data or 'start_date' not in data or 'end_date' not in data:
            return jsonify({
                'message': 'Missing required fields: start_date, end_date',
                'example': {
                    'start_date': '2024-12-01',
                    'end_date': '2024-12-31'
                }
            }), 400
        
        try:
            start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({
                'message': 'Invalid date format. Use YYYY-MM-DD',
                'example': '2024-12-01'
            }), 400
        
        # التحقق من صحة الفترة
        if start_date > end_date:
            return jsonify({
                'message': 'Start date cannot be after end date'
            }), 400
        
        if end_date > date.today():
            return jsonify({
                'message': 'End date cannot be in the future'
            }), 400
        
        # البحث عن الموظف
        employee = Employee.query.get(employee_id)
        if not employee:
            return jsonify({
                'message': f'Employee with ID {employee_id} not found'
            }), 404
        
        # حساب الراتب
        salary_result = calculate_employee_salary_period(employee, start_date, end_date)
        
        # تجهيز البيانات للنموذج
        system_type = salary_result.get('system_type', 'none')
        breakdown_details = get_breakdown_details(salary_result, system_type)
        
        context = {
            'employee_name': employee.full_name,
            'employee_id': employee.id,
            'fingerprint_id': employee.fingerprint_id or '-',
            'position': salary_result.get('position', '-'),
            'system_type': get_system_type_display(system_type),
            'period_start': start_date.strftime('%Y-%m-%d'),
            'period_end': end_date.strftime('%Y-%m-%d'),
            'period_days': salary_result['period_info']['total_days'],
            'basic_salary': float(salary_result['basic_salary']),
            'allowances': float(salary_result['allowances']),
            'additions': float(salary_result['additions']),
            'deductions': float(salary_result['deductions']),
            'net_salary': float(salary_result['net_salary']),
            'system_details': bool(breakdown_details),
            'breakdown_title': f"تفاصيل {get_system_type_display(system_type)}",
            'breakdown_details': breakdown_details,
            'notes': salary_result.get('notes', ''),
            'current_date': datetime.now().strftime('%Y-%m-%d'),
            'generated_at': f"تم التوليد في: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        }
        
        # توليد HTML
        html_content = render_template_string(PAYSLIP_HTML_TEMPLATE, **context)
        
        return html_content, 200, {
            'Content-Type': 'text/html; charset=utf-8',
            'Content-Disposition': f'inline; filename="payslip_{employee_id}.html"'
        }
        
    except Exception as e:
        print(f"Error generating payslip: {str(e)}")
        return jsonify({
            'message': 'Error generating payslip',
            'error': str(e)
        }), 500

@payroll_bp.route('/api/payslip/<int:employee_id>/preview', methods=['POST'])
@token_required
def preview_payslip_data(user, employee_id):
    """
    معاينة بيانات الراتب (JSON)
    
    URL: POST /api/payslip/2/preview
    """
    try:
        data = request.get_json()
        
        if not data or 'start_date' not in data or 'end_date' not in data:
            return jsonify({
                'message': 'Missing required fields: start_date, end_date'
            }), 400
        
        try:
            start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({
                'message': 'Invalid date format. Use YYYY-MM-DD'
            }), 400
        
        if start_date > end_date:
            return jsonify({
                'message': 'Start date cannot be after end date'
            }), 400
        
        # البحث عن الموظف
        employee = Employee.query.get(employee_id)
        if not employee:
            return jsonify({
                'message': f'Employee with ID {employee_id} not found'
            }), 404
        
        # حساب الراتب
        salary_result = calculate_employee_salary_period(employee, start_date, end_date)
        
        # تحضير البيانات
        preview_data = {
            'status': 'success',
            'employee': {
                'id': employee.id,
                'full_name': employee.full_name,
                'fingerprint_id': employee.fingerprint_id,
                'position': salary_result.get('position', '-')
            },
            'salary_calculation': salary_result,
            'generated_at': datetime.now().isoformat()
        }
        
        return jsonify(preview_data), 200
        
    except Exception as e:
        return jsonify({
            'message': 'Error previewing payslip',
            'error': str(e)
        }), 500

@payroll_bp.route('/api/payslip/batch/html', methods=['POST'])
@token_required
def generate_batch_payslips_html(user):
    """
    إنشاء صفحة HTML تحتوي على عدة وصلات راتب
    
    URL: POST /api/payslip/batch/html
    
    البيانات:
    {
        "employee_ids": [1, 2, 3],
        "start_date": "2024-12-01",
        "end_date": "2024-12-31"
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'employee_ids' not in data:
            return jsonify({
                'message': 'Missing required field: employee_ids (array of employee IDs)'
            }), 400
        
        try:
            start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({
                'message': 'Invalid date format. Use YYYY-MM-DD'
            }), 400
        
        employee_ids = data.get('employee_ids', [])
        if not employee_ids or not isinstance(employee_ids, list):
            return jsonify({
                'message': 'employee_ids must be a non-empty list'
            }), 400
        
        # توليد وصلات متعددة
        payslips_html_parts = []
        errors = []
        
        for emp_id in employee_ids:
            try:
                employee = Employee.query.get(emp_id)
                if not employee:
                    errors.append(f"Employee {emp_id} not found")
                    continue
                
                salary_result = calculate_employee_salary_period(employee, start_date, end_date)
                
                system_type = salary_result.get('system_type', 'none')
                breakdown_details = get_breakdown_details(salary_result, system_type)
                
                context = {
                    'employee_name': employee.full_name,
                    'employee_id': employee.id,
                    'fingerprint_id': employee.fingerprint_id or '-',
                    'position': salary_result.get('position', '-'),
                    'system_type': get_system_type_display(system_type),
                    'period_start': start_date.strftime('%Y-%m-%d'),
                    'period_end': end_date.strftime('%Y-%m-%d'),
                    'period_days': salary_result['period_info']['total_days'],
                    'basic_salary': float(salary_result['basic_salary']),
                    'allowances': float(salary_result['allowances']),
                    'additions': float(salary_result['additions']),
                    'deductions': float(salary_result['deductions']),
                    'net_salary': float(salary_result['net_salary']),
                    'system_details': bool(breakdown_details),
                    'breakdown_title': f"تفاصيل {get_system_type_display(system_type)}",
                    'breakdown_details': breakdown_details,
                    'notes': salary_result.get('notes', ''),
                    'current_date': datetime.now().strftime('%Y-%m-%d'),
                    'generated_at': f"تم التوليد في: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                }
                
                payslip_html = render_template_string(PAYSLIP_HTML_TEMPLATE, **context)
                payslips_html_parts.append(payslip_html)
                
            except Exception as e:
                errors.append(f"Error processing employee {emp_id}: {str(e)}")
                continue
        
        if not payslips_html_parts:
            return jsonify({
                'message': 'Could not generate any payslips',
                'errors': errors
            }), 400
        
        # دمج جميع الوصلات
        batch_html = f"""
        <!DOCTYPE html>
        <html lang="ar" dir="rtl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>وصلات الراتب - دفعة متعددة</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #f5f5f5;
                    padding: 20px;
                }}
                .batch-controls {{
                    text-align: center;
                    margin-bottom: 20px;
                    display: flex;
                    gap: 10px;
                    justify-content: center;
                    flex-wrap: wrap;
                }}
                .btn {{
                    padding: 10px 20px;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 14px;
                    font-weight: bold;
                }}
                .btn-print {{
                    background-color: #27ae60;
                    color: white;
                }}
                .btn-print:hover {{
                    background-color: #229954;
                }}
                @media print {{
                    .batch-controls {{ display: none !important; }}
                    .page-separator {{ page-break-after: always; }}
                }}
            </style>
        </head>
        <body>
            <div class="batch-controls">
                <button class="btn btn-print" onclick="window.print()">🖨️ طباعة الكل</button>
            </div>
        """
        
        for i, payslip in enumerate(payslips_html_parts):
            if i > 0:
                batch_html += '<div class="page-separator"></div>'
            batch_html += payslip
        
        batch_html += """
        </body>
        </html>
        """
        
        return batch_html, 200, {
            'Content-Type': 'text/html; charset=utf-8',
            'Content-Disposition': 'inline; filename="payslips_batch.html"'
        }
        
    except Exception as e:
        print(f"Error generating batch payslips: {str(e)}")
        return jsonify({
            'message': 'Error generating batch payslips',
            'error': str(e)
        }), 500
