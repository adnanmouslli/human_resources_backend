from flask import Blueprint, request, jsonify
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
            'system_details': system_details
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
                db.func.date(Attendance.checkInTime).between(start_date, end_date)
            )
            .order_by(db.func.date(Attendance.checkInTime), Attendance.checkInTime)
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
                db.func.date(Attendance.checkInTime).between(start_date, end_date)
            )
            .order_by(db.func.date(Attendance.checkInTime), Attendance.checkInTime)
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