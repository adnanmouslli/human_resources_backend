from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, send_file
from sqlalchemy import func, cast, Date
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib import colors
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping
import io
import os
from app import db
from app.models import Attendance, Employee, Shift, JobTitle, Profession
from app.models.user import User
from app.utils import token_required

# إضافة دعم للنصوص العربية
try:
    from arabic_reshaper import reshape
    from bidi.algorithm import get_display
    ARABIC_SUPPORT = True
except ImportError:
    print("Warning: arabic_reshaper and python-bidi not installed. Arabic text may not display correctly.")
    print("Install with: pip install arabic-reshaper python-bidi")
    ARABIC_SUPPORT = False

# إضافة blueprint للتقارير
reports_bp = Blueprint('reports', __name__)

def process_arabic_text(text):
    """معالجة النص العربي ليظهر بشكل صحيح في PDF"""
    if not text:
        return ""
    
    # تحويل إلى نص أولاً
    text_str = str(text)
    
    # إذا كان النص يحتوي على أرقام فقط أو أحرف إنجليزية فقط، لا نحتاج معالجة
    if text_str.isdigit() or all(ord(c) < 128 for c in text_str):
        return text_str
    
    if not ARABIC_SUPPORT:
        return text_str
    
    try:
        # معالجة النص العربي
        reshaped_text = reshape(text_str)
        bidi_text = get_display(reshaped_text)
        return bidi_text
    except Exception as e:
        print(f"Error processing Arabic text '{text_str}': {e}")
        return text_str

def register_arabic_fonts():
    """تسجيل الخطوط العربية مع معالجة أفضل"""
    try:
        # مسارات الخطوط المحتملة مرتبة حسب الأولوية
        font_paths = [
            # خط محلي مخصص للعربية
            os.path.join(os.path.dirname(__file__), '..', 'fonts', 'NotoSansArabic-Regular.ttf'),
            os.path.join(os.path.dirname(__file__), '..', 'fonts', 'Arial-Unicode-MS.ttf'),
            # خطوط النظام - Linux
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/TTF/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            # خطوط النظام - macOS
            '/System/Library/Fonts/Arial.ttf',
            '/System/Library/Fonts/Helvetica.ttc',
            # خطوط النظام - Windows
            'C:/Windows/Fonts/arial.ttf',
            'C:/Windows/Fonts/tahoma.ttf',
            'C:/Windows/Fonts/calibri.ttf',
        ]
        
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    # تسجيل الخط العادي
                    pdfmetrics.registerFont(TTFont('Arabic', font_path))
                    
                    # محاولة تسجيل الخط العريض إذا وجد
                    bold_path = font_path.replace('.ttf', '-Bold.ttf').replace('-Regular', '-Bold')
                    if os.path.exists(bold_path):
                        pdfmetrics.registerFont(TTFont('Arabic-Bold', bold_path))
                    else:
                        # استخدام نفس الخط للعريض
                        pdfmetrics.registerFont(TTFont('Arabic-Bold', font_path))
                    
                    # إضافة التمثيل للخطوط
                    addMapping('Arabic', 0, 0, 'Arabic')      # عادي
                    addMapping('Arabic', 1, 0, 'Arabic-Bold') # عريض
                    addMapping('Arabic', 0, 1, 'Arabic')      # مائل
                    addMapping('Arabic', 1, 1, 'Arabic-Bold') # عريض مائل
                    
                    print(f"Successfully registered Arabic font: {font_path}")
                    return True
                except Exception as e:
                    print(f"Failed to register font {font_path}: {e}")
                    continue
                    
    except Exception as e:
        print(f"Error in font registration: {e}")
    
    print("Warning: No Arabic font found, using default font")
    return False

# تسجيل الخطوط عند تحميل المودول
ARABIC_FONT_AVAILABLE = register_arabic_fonts()

def get_font_name(bold=False):
    """الحصول على اسم الخط المناسب"""
    if ARABIC_FONT_AVAILABLE:
        return 'Arabic-Bold' if bold else 'Arabic'
    else:
        return 'Helvetica-Bold' if bold else 'Helvetica'

class NumberedCanvas(canvas.Canvas):
    """كلاس لإضافة أرقام الصفحات مع دعم العربية محسن"""
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for (page_num, page_state) in enumerate(self._saved_page_states):
            self.__dict__.update(page_state)
            self.draw_page_number(page_num + 1, num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_num, total_pages):
        font_name = get_font_name()
        self.setFont(font_name, 9)
        
        # نص رقم الصفحة باللغة العربية
        page_text = f"صفحة {page_num} من {total_pages}"
        processed_text = process_arabic_text(page_text)
        
        # رسم النص في الزاوية السفلى اليمنى
        self.drawRightString(letter[0] - 30, 30, processed_text)

def create_arabic_paragraph_style(base_style, font_size=12, bold=False):
    """إنشاء نمط فقرة يدعم العربية بشكل محسن"""
    font_name = get_font_name(bold)
    
    return ParagraphStyle(
        f'Arabic_{base_style.name}{"_Bold" if bold else ""}',
        parent=base_style,
        fontName=font_name,
        fontSize=font_size,
        leading=font_size * 1.2,
        alignment=TA_RIGHT,  # محاذاة يمين للعربية
        wordWrap='RTL',      # التفاف الكلمات من اليمين لليسار
        spaceAfter=6,
        spaceBefore=6
    )

def create_arabic_table_style(data):
    """إنشاء نمط جدول يدعم العربية بشكل محسن"""
    font_name = get_font_name()
    font_name_bold = get_font_name(True)
    
    base_style = [
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),  # محاذاة يمين للعربية
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]
    
    # إضافة تنسيق خاص للرأس
    if len(data) > 0:
        header_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), font_name_bold),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
        ]
        base_style.extend(header_style)
    
    return TableStyle(base_style)

def process_table_data(data):
    """معالجة بيانات الجدول لدعم العربية بشكل شامل"""
    processed_data = []
    for row in data:
        processed_row = []
        for cell in row:
            # معالجة كل خلية على حدة
            if cell is None:
                processed_cell = ""
            else:
                processed_cell = process_arabic_text(str(cell))
            processed_row.append(processed_cell)
        processed_data.append(processed_row)
    return processed_data

def time_to_seconds(t):
    """تحويل كائن الوقت إلى ثوان منذ منتصف الليل"""
    if t is None:
        return 0
    return t.hour * 3600 + t.minute * 60 + t.second

def seconds_to_time_string(seconds):
    """تحويل الثوان إلى نص وقت قابل للقراءة"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{int(hours):02d}:{int(minutes):02d}"

def calculate_work_hours(check_in, check_out):
    """حساب ساعات العمل بين وقت الدخول والخروج"""
    if not check_in or not check_out:
        return 0, "00:00"
    
    work_seconds = time_to_seconds(check_out) - time_to_seconds(check_in)
    if work_seconds < 0:  # في حالة العمل عبر منتصف الليل
        work_seconds += 24 * 3600
    
    return work_seconds, seconds_to_time_string(work_seconds)

def get_status_text(status):
    """الحصول على نص الحالة باللغة العربية"""
    status_map = {
        'present': 'حاضر',
        'absent': 'غائب',
        'late': 'متأخر',
        'incomplete': 'غير مكتمل',
        'early_leave': 'انصراف مبكر'
    }
    return status_map.get(status, status)

def get_employee_type_text(emp_type):
    """الحصول على نص نوع الموظف باللغة العربية"""
    type_map = {
        'permanent': 'دائم',
        'temporary': 'مؤقت',
        'contract': 'تعاقد',
        'intern': 'متدرب'
    }
    return type_map.get(emp_type, emp_type)

def get_work_system_text(work_system):
    """الحصول على نص نظام العمل باللغة العربية"""
    system_map = {
        'shift': 'ورديات',
        'hours': 'ساعات',
        'flexible': 'مرن'
    }
    return system_map.get(work_system, work_system)

def process_daily_attendance(employee, date, attendances):
    """معالجة سجلات الحضور ليوم واحد مع ترجمة محسنة"""
    if not attendances:
        return {
            'date': date.strftime('%Y-%m-%d'),
            'status': 'غائب',
            'first_check_in': '-',
            'last_check_out': '-',
            'total_work_hours': '00:00',
            'total_break_time': '00:00',
            'periods': [],
            'notes': 'لا يوجد سجلات حضور'
        }

    # ترتيب السجلات حسب وقت الإنشاء
    attendances.sort(key=lambda x: x.createdAt)
    
    periods = []
    total_work_seconds = 0
    
    for att in attendances:
        if att.checkInTime and att.checkOutTime:
            work_seconds, work_time_str = calculate_work_hours(att.checkInTime, att.checkOutTime)
            total_work_seconds += work_seconds
            
            periods.append({
                'check_in': att.checkInTime.strftime('%H:%M'),
                'check_out': att.checkOutTime.strftime('%H:%M'),
                'work_time': work_time_str,
                'check_in_reason': att.checkInReason or '-',
                'check_out_reason': att.checkOutReason or '-'
            })
        else:
            periods.append({
                'check_in': att.checkInTime.strftime('%H:%M') if att.checkInTime else '-',
                'check_out': att.checkOutTime.strftime('%H:%M') if att.checkOutTime else '-',
                'work_time': '00:00',
                'check_in_reason': att.checkInReason or '-',
                'check_out_reason': att.checkOutReason or 'لم يسجل الخروج'
            })

    # حساب وقت الاستراحة
    total_break_seconds = 0
    if len(periods) > 1:
        for i in range(1, len(attendances)):
            if (attendances[i-1].checkOutTime and attendances[i].checkInTime):
                break_seconds = (time_to_seconds(attendances[i].checkInTime) - 
                               time_to_seconds(attendances[i-1].checkOutTime))
                if break_seconds > 0:
                    total_break_seconds += break_seconds

    # تحديد حالة الحضور
    status = 'حاضر'
    if any(not att.checkOutTime for att in attendances):
        status += ' (لم يسجل خروج)'
    
    # التحقق من الالتزام بالوردية
    shift_note = ""
    if employee.work_system == 'shift' and employee.shift_id:
        shift = Shift.query.get(employee.shift_id)
        if shift and attendances:
            first_checkin = min(att.checkInTime for att in attendances if att.checkInTime)
            allowed_delay = timedelta(minutes=shift.allowed_delay_minutes)
            shift_start_seconds = time_to_seconds(shift.start_time)
            actual_checkin_seconds = time_to_seconds(first_checkin)
            
            if actual_checkin_seconds > shift_start_seconds + allowed_delay.total_seconds():
                delay_minutes = (actual_checkin_seconds - shift_start_seconds) // 60
                shift_note = f"تأخير {delay_minutes:.0f} دقيقة"

    return {
        'date': date.strftime('%Y-%m-%d'),
        'status': status,
        'first_check_in': min(att.checkInTime for att in attendances if att.checkInTime).strftime('%H:%M') if any(att.checkInTime for att in attendances) else '-',
        'last_check_out': max(att.checkOutTime for att in attendances if att.checkOutTime).strftime('%H:%M') if any(att.checkOutTime for att in attendances) else '-',
        'total_work_hours': seconds_to_time_string(total_work_seconds),
        'total_break_time': seconds_to_time_string(total_break_seconds),
        'periods': periods,
        'notes': shift_note
    }

def create_employee_report_pdf(employee, start_date, end_date, daily_data, summary_stats):
    """إنشاء تقرير PDF لموظف محدد مع دعم عربي محسن"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter, 
        topMargin=1*inch, 
        rightMargin=0.5*inch, 
        leftMargin=0.5*inch,
        bottomMargin=0.75*inch
    )
    
    # الحصول على الأنماط
    styles = getSampleStyleSheet()
    
    # إنشاء أنماط مخصصة تدعم العربية
    title_style = create_arabic_paragraph_style(styles['Heading1'], font_size=18, bold=True)
    title_style.alignment = TA_CENTER
    title_style.textColor = colors.darkblue
    title_style.spaceAfter = 30
    
    heading_style = create_arabic_paragraph_style(styles['Heading2'], font_size=14, bold=True)
    heading_style.textColor = colors.darkgreen
    heading_style.spaceAfter = 15
    
    # بناء محتوى التقرير
    story = []
    
    # العنوان الرئيسي
    title_text = f"تقرير الحضور والانصراف - {employee.full_name}"
    processed_title = process_arabic_text(title_text)
    story.append(Paragraph(processed_title, title_style))
    story.append(Spacer(1, 20))
    
    # معلومات الموظف
    heading_text = process_arabic_text("معلومات الموظف")
    story.append(Paragraph(heading_text, heading_style))
    
    # تجهيز معلومات الموظف مع الترجمة
    employee_info = [
        [process_arabic_text('رقم الموظف:'), str(employee.id)],
        [process_arabic_text('الاسم الكامل:'), process_arabic_text(employee.full_name)],
        [process_arabic_text('المنصب:'), process_arabic_text(employee.position or '-')],
        [process_arabic_text('نوع الموظف:'), process_arabic_text(get_employee_type_text(employee.employee_type))],
        [process_arabic_text('نظام العمل:'), process_arabic_text(get_work_system_text(employee.work_system))],
        [process_arabic_text('فترة التقرير:'), f"{start_date.strftime('%Y-%m-%d')} إلى {end_date.strftime('%Y-%m-%d')}"]
    ]
    
    # إضافة معلومات الوردية إذا كان نظام ورديات
    if employee.work_system == 'shift' and employee.shift_id:
        shift = Shift.query.get(employee.shift_id)
        if shift:
            employee_info.extend([
                [process_arabic_text('بداية الوردية:'), shift.start_time.strftime('%H:%M')],
                [process_arabic_text('نهاية الوردية:'), shift.end_time.strftime('%H:%M')],
                [process_arabic_text('التأخير المسموح:'), f"{shift.allowed_delay_minutes} دقيقة"]
            ])
    
    # إنشاء جدول معلومات الموظف
    employee_table = Table(employee_info, colWidths=[2*inch, 4*inch])
    employee_table.setStyle(create_arabic_table_style(employee_info))
    employee_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
    ]))
    
    story.append(employee_table)
    story.append(Spacer(1, 30))
    
    # الإحصائيات العامة
    summary_heading = process_arabic_text("ملخص الإحصائيات")
    story.append(Paragraph(summary_heading, heading_style))
    
    summary_data = [
        [process_arabic_text('إجمالي أيام العمل:'), str(summary_stats['total_work_days'])],
        [process_arabic_text('إجمالي أيام الغياب:'), str(summary_stats['total_absent_days'])],
        [process_arabic_text('إجمالي ساعات العمل:'), summary_stats['total_work_hours']],
        [process_arabic_text('متوسط الساعات اليومية:'), summary_stats['average_daily_hours']],
        [process_arabic_text('أيام التأخير:'), str(summary_stats['late_days'])],
        [process_arabic_text('أيام بدون تسجيل خروج:'), str(summary_stats['incomplete_days'])]
    ]
    
    summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
    summary_table.setStyle(create_arabic_table_style(summary_data))
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightblue),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
    ]))
    
    story.append(summary_table)
    story.append(Spacer(1, 30))
    
    # التفاصيل اليومية
    daily_heading = process_arabic_text("التفاصيل اليومية")
    story.append(Paragraph(daily_heading, heading_style))
    
    # جدول التفاصيل اليومية مع معالجة شاملة
    daily_headers = [
        process_arabic_text('التاريخ'), 
        process_arabic_text('الحالة'), 
        process_arabic_text('أول دخول'), 
        process_arabic_text('آخر خروج'), 
        process_arabic_text('ساعات العمل'), 
        process_arabic_text('وقت الاستراحة'), 
        process_arabic_text('ملاحظات')
    ]
    daily_table_data = [daily_headers]
    
    for day_data in daily_data:
        daily_table_data.append([
            day_data['date'],
            process_arabic_text(day_data['status']),
            day_data['first_check_in'],
            day_data['last_check_out'],
            day_data['total_work_hours'],
            day_data['total_break_time'],
            process_arabic_text(day_data['notes'] if day_data['notes'] else '-')
        ])
    
    daily_table = Table(daily_table_data, colWidths=[0.8*inch, 1*inch, 0.8*inch, 0.8*inch, 0.7*inch, 0.7*inch, 1.4*inch])
    daily_table.setStyle(create_arabic_table_style(daily_table_data))
    daily_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
    ]))
    
    story.append(daily_table)
    story.append(PageBreak())
    
    # تفاصيل الفترات للأيام التي تحتوي على عدة فترات
    periods_heading = process_arabic_text("تفاصيل فترات العمل")
    story.append(Paragraph(periods_heading, heading_style))
    
    has_multiple_periods = False
    for day_data in daily_data:
        if len(day_data['periods']) > 1:
            has_multiple_periods = True
            day_heading_style = create_arabic_paragraph_style(styles['Heading3'], font_size=12, bold=True)
            day_title = process_arabic_text(f"التاريخ: {day_data['date']}")
            story.append(Paragraph(day_title, day_heading_style))
            
            periods_headers = [
                process_arabic_text('الفترة'), 
                process_arabic_text('الدخول'), 
                process_arabic_text('الخروج'), 
                process_arabic_text('وقت العمل'), 
                process_arabic_text('سبب الدخول'), 
                process_arabic_text('سبب الخروج')
            ]
            periods_data = [periods_headers]
            
            for i, period in enumerate(day_data['periods'], 1):
                periods_data.append([
                    str(i),
                    period['check_in'],
                    period['check_out'],
                    period['work_time'],
                    process_arabic_text(period['check_in_reason']),
                    process_arabic_text(period['check_out_reason'])
                ])
            
            periods_table = Table(periods_data, colWidths=[0.6*inch, 0.8*inch, 0.8*inch, 0.8*inch, 1.5*inch, 1.5*inch])
            periods_table.setStyle(create_arabic_table_style(periods_data))
            periods_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
            ]))
            
            story.append(periods_table)
            story.append(Spacer(1, 20))
    
    if not has_multiple_periods:
        no_periods_style = create_arabic_paragraph_style(styles['Normal'], font_size=12)
        no_periods_text = process_arabic_text("لا توجد أيام بفترات عمل متعددة في هذا التقرير")
        story.append(Paragraph(no_periods_text, no_periods_style))
    
    # بناء المستند
    doc.build(story, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer

def create_general_report_pdf(start_date, end_date, employees_data, general_stats):
    """إنشاء تقرير PDF عام لجميع الموظفين مع دعم عربي محسن"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4, 
        topMargin=1*inch, 
        rightMargin=0.5*inch, 
        leftMargin=0.5*inch,
        bottomMargin=0.75*inch
    )
    
    styles = getSampleStyleSheet()
    
    # إنشاء أنماط مخصصة تدعم العربية
    title_style = create_arabic_paragraph_style(styles['Heading1'], font_size=16, bold=True)
    title_style.alignment = TA_CENTER
    title_style.textColor = colors.darkblue
    title_style.spaceAfter = 30
    
    heading_style = create_arabic_paragraph_style(styles['Heading2'], font_size=12, bold=True)
    heading_style.textColor = colors.darkgreen
    heading_style.spaceAfter = 15
    
    story = []
    
    # العنوان الرئيسي
    title_text = f"التقرير العام للحضور والانصراف ({start_date.strftime('%Y-%m-%d')} إلى {end_date.strftime('%Y-%m-%d')})"
    processed_title = process_arabic_text(title_text)
    story.append(Paragraph(processed_title, title_style))
    story.append(Spacer(1, 20))
    
    # الإحصائيات العامة
    general_heading = process_arabic_text("الإحصائيات العامة")
    story.append(Paragraph(general_heading, heading_style))
    
    general_summary = [
        [process_arabic_text('إجمالي الموظفين:'), str(general_stats['total_employees'])],
        [process_arabic_text('إجمالي أيام العمل:'), str(general_stats['total_work_days'])],
        [process_arabic_text('إجمالي أيام الغياب:'), str(general_stats['total_absent_days'])],
        [process_arabic_text('معدل الحضور:'), f"{general_stats['attendance_rate']:.1f}%"],
        [process_arabic_text('إجمالي ساعات العمل:'), general_stats['total_work_hours']],
        [process_arabic_text('متوسط الساعات لكل موظف:'), general_stats['avg_hours_per_employee']]
    ]
    
    general_table = Table(general_summary, colWidths=[3*inch, 2*inch])
    general_table.setStyle(create_arabic_table_style(general_summary))
    general_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightblue),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
    ]))
    
    story.append(general_table)
    story.append(Spacer(1, 30))
    
    # ملخص الموظفين
    employees_heading = process_arabic_text("ملخص الموظفين")
    story.append(Paragraph(employees_heading, heading_style))
    
    employees_headers = [
        process_arabic_text('الرقم'), 
        process_arabic_text('الاسم'), 
        process_arabic_text('النوع'), 
        process_arabic_text('أيام العمل'), 
        process_arabic_text('أيام الغياب'), 
        process_arabic_text('إجمالي الساعات'), 
        process_arabic_text('متوسط يومي'), 
        process_arabic_text('أيام التأخير')
    ]
    employees_table_data = [employees_headers]
    
    for emp_data in employees_data:
        employee_name = emp_data['employee']['full_name']
        if len(employee_name) > 15:
            employee_name = employee_name[:15] + '...'
        
        employee_type_text = get_employee_type_text(emp_data['employee']['employee_type'])
        
        employees_table_data.append([
            str(emp_data['employee']['id']),
            process_arabic_text(employee_name),
            process_arabic_text(employee_type_text),
            str(emp_data['summary']['total_work_days']),
            str(emp_data['summary']['total_absent_days']),
            emp_data['summary']['total_work_hours'],
            emp_data['summary']['average_daily_hours'],
            str(emp_data['summary']['late_days'])
        ])
    
    employees_table = Table(employees_table_data, colWidths=[0.4*inch, 1.6*inch, 0.6*inch, 0.6*inch, 0.6*inch, 0.8*inch, 0.7*inch, 0.7*inch])
    employees_table.setStyle(create_arabic_table_style(employees_table_data))
    employees_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    
    story.append(employees_table)
    story.append(PageBreak())
    
    # التفاصيل اليومية لكل موظف (ملخص)
    subheading_style = create_arabic_paragraph_style(styles['Heading3'], font_size=11, bold=True)
    
    for i, emp_data in enumerate(employees_data):
        emp_title = process_arabic_text(f"الموظف: {emp_data['employee']['full_name']}")
        story.append(Paragraph(emp_title, subheading_style))
        
        # ملخص الموظف
        emp_summary_data = [
            [process_arabic_text('الرقم:'), str(emp_data['employee']['id'])],
            [process_arabic_text('المنصب:'), process_arabic_text(emp_data['employee']['position'])],
            [process_arabic_text('أيام العمل:'), str(emp_data['summary']['total_work_days'])],
            [process_arabic_text('أيام الغياب:'), str(emp_data['summary']['total_absent_days'])],
            [process_arabic_text('إجمالي الساعات:'), emp_data['summary']['total_work_hours']]
        ]
        
        emp_summary_table = Table(emp_summary_data, colWidths=[1*inch, 2*inch])
        emp_summary_table.setStyle(create_arabic_table_style(emp_summary_data))
        emp_summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        
        story.append(emp_summary_table)
        story.append(Spacer(1, 15))
        
        # جدول مختصر للحضور اليومي
        daily_summary_headers = [
            process_arabic_text('التاريخ'), 
            process_arabic_text('الحالة'), 
            process_arabic_text('الدخول'), 
            process_arabic_text('الخروج'), 
            process_arabic_text('ساعات العمل')
        ]
        daily_summary_data = [daily_summary_headers]
        
        # عرض أول 10 أيام فقط لتوفير المساحة
        display_days = emp_data['daily_data'][:10]
        
        for day_data in display_days:
            status = day_data['status']
            if len(status) > 12:
                status = status[:12] + '...'
            
            daily_summary_data.append([
                day_data['date'],
                process_arabic_text(status),
                day_data['first_check_in'],
                day_data['last_check_out'],
                day_data['total_work_hours']
            ])
        
        # إضافة صف يشير لوجود المزيد من البيانات
        if len(emp_data['daily_data']) > 10:
            more_days_text = process_arabic_text(f"و {len(emp_data['daily_data']) - 10} أيام أخرى")
            daily_summary_data.append([
                '...', more_days_text, '...', '...', '...'
            ])
        
        daily_summary_table = Table(daily_summary_data, colWidths=[0.8*inch, 1.2*inch, 0.7*inch, 0.7*inch, 0.8*inch])
        daily_summary_table.setStyle(create_arabic_table_style(daily_summary_data))
        daily_summary_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        
        story.append(daily_summary_table)
        story.append(Spacer(1, 20))
        
        # إضافة فاصل صفحة بين الموظفين إذا لم يكن آخر موظف
        if i < len(employees_data) - 1:
            story.append(PageBreak())
    
    doc.build(story, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer

@reports_bp.route('/api/reports/employee/<int:employee_id>', methods=['GET'])
@token_required
def generate_employee_report(user_id, employee_id):
    """إنشاء تقرير PDF لموظف محدد"""
    try:
        # الحصول على المعاملات
        start_date_str = request.args.get('startDate')
        end_date_str = request.args.get('endDate')
        
        if not start_date_str or not end_date_str:
            return jsonify({'message': 'Start date and end date are required'}), 400
        
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'message': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        if start_date > end_date:
            return jsonify({'message': 'Start date cannot be after end date'}), 400
        
        # الحصول على الموظف
        employee = Employee.query.get(employee_id)
        if not employee:
            return jsonify({'message': 'Employee not found'}), 404
        
        # الحصول على سجلات الحضور - تم تصحيح الاستعلام
        attendances = Attendance.query.filter(
            Attendance.empId == employee_id,
            Attendance.createdAt >= start_date,
            Attendance.createdAt <= end_date
        ).order_by(Attendance.createdAt).all()
        
        # معالجة البيانات اليومية
        daily_data = []
        current_date = start_date
        total_work_seconds = 0
        work_days = 0
        absent_days = 0
        late_days = 0
        incomplete_days = 0
        
        while current_date <= end_date:
            # الحصول على سجلات هذا اليوم - تم تصحيح المقارنة
            day_attendances = [
                att for att in attendances 
                if att.createdAt == current_date
            ]
            
            day_data = process_daily_attendance(employee, current_date, day_attendances)
            daily_data.append(day_data)
            
            # تحديث الإحصائيات
            if day_attendances:
                work_days += 1
                # تحويل وقت العمل من نص إلى ثوان
                work_time_parts = day_data['total_work_hours'].split(':')
                day_work_seconds = int(work_time_parts[0]) * 3600 + int(work_time_parts[1]) * 60
                total_work_seconds += day_work_seconds
                
                # عد الأيام المتأخرة
                if 'تأخير' in day_data['notes']:
                    late_days += 1
                
                # عد الأيام غير المكتملة
                if 'لم يسجل خروج' in day_data['status']:
                    incomplete_days += 1
            else:
                absent_days += 1
            
            current_date += timedelta(days=1)
        
        # حساب الإحصائيات
        average_daily_seconds = total_work_seconds / work_days if work_days > 0 else 0
        
        summary_stats = {
            'total_work_days': work_days,
            'total_absent_days': absent_days,
            'total_work_hours': seconds_to_time_string(total_work_seconds),
            'average_daily_hours': seconds_to_time_string(average_daily_seconds),
            'late_days': late_days,
            'incomplete_days': incomplete_days
        }
        
        # إنشاء PDF
        pdf_buffer = create_employee_report_pdf(employee, start_date, end_date, daily_data, summary_stats)
        
        # إرسال الملف
        filename = f"attendance_report_{employee.full_name}_{start_date_str}_to_{end_date_str}.pdf"
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        print(f"Error generating employee report: {str(e)}")
        return jsonify({'message': 'Error generating report', 'error': str(e)}), 500
    
@reports_bp.route('/api/reports/general', methods=['GET'])
@token_required
def generate_general_report(user_id):
    """إنشاء تقرير PDF عام لجميع الموظفين"""
    try:
        # الحصول على المعاملات
        start_date_str = request.args.get('startDate')
        end_date_str = request.args.get('endDate')
        
        if not start_date_str or not end_date_str:
            return jsonify({'message': 'Start date and end date are required'}), 400
        
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'message': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        if start_date > end_date:
            return jsonify({'message': 'Start date cannot be after end date'}), 400
        
        # الحصول على المستخدم وصلاحياته
        user = User.query.get(user_id.id)
        if not user:
            return jsonify({'message': 'User not found'}), 404
        
        # الحصول على الموظفين المسموح للمستخدم برؤيتهم
        accessible_employees = user.get_accessible_employees()
        
        if not accessible_employees:
            return jsonify({'message': 'No accessible employees found'}), 404
        
        employees_data = []
        general_total_work_seconds = 0
        general_total_work_days = 0
        general_total_absent_days = 0
        
        for employee in accessible_employees:
            # الحصول على سجلات الحضور للموظف - تم إصلاح التحويل هنا
            attendances = Attendance.query.filter(
                Attendance.empId == employee.id,
                Attendance.createdAt >= start_date,
                Attendance.createdAt <= end_date
            ).order_by(Attendance.createdAt).all()
            
            # معالجة البيانات اليومية للموظف
            daily_data = []
            current_date = start_date
            employee_total_work_seconds = 0
            employee_work_days = 0
            employee_absent_days = 0
            employee_late_days = 0
            employee_incomplete_days = 0
            
            while current_date <= end_date:
                # الحصول على سجلات هذا اليوم - تم إصلاح المقارنة هنا
                day_attendances = [
                    att for att in attendances 
                    if att.createdAt == current_date
                ]
                
                day_data = process_daily_attendance(employee, current_date, day_attendances)
                daily_data.append(day_data)
                
                # تحديث الإحصائيات
                if day_attendances:
                    employee_work_days += 1
                    # تحويل وقت العمل من نص إلى ثوان
                    work_time_parts = day_data['total_work_hours'].split(':')
                    day_work_seconds = int(work_time_parts[0]) * 3600 + int(work_time_parts[1]) * 60
                    employee_total_work_seconds += day_work_seconds
                    
                    # عد الأيام المتأخرة
                    if 'تأخير' in day_data['notes']:
                        employee_late_days += 1
                    
                    # عد الأيام غير المكتملة
                    if 'لم يسجل خروج' in day_data['status']:
                        employee_incomplete_days += 1
                else:
                    employee_absent_days += 1
                
                current_date += timedelta(days=1)
            
            # حساب المتوسط اليومي للموظف
            employee_average_daily_seconds = employee_total_work_seconds / employee_work_days if employee_work_days > 0 else 0
            
            # إحصائيات الموظف
            employee_summary = {
                'total_work_days': employee_work_days,
                'total_absent_days': employee_absent_days,
                'total_work_hours': seconds_to_time_string(employee_total_work_seconds),
                'average_daily_hours': seconds_to_time_string(employee_average_daily_seconds),
                'late_days': employee_late_days,
                'incomplete_days': employee_incomplete_days
            }
            
            # إضافة بيانات الموظف إلى القائمة
            employee_data = {
                'employee': {
                    'id': employee.id,
                    'full_name': employee.full_name,
                    'employee_type': employee.employee_type,
                    'position': employee.position or '-',
                    'work_system': employee.work_system
                },
                'daily_data': daily_data,
                'summary': employee_summary
            }
            
            employees_data.append(employee_data)
            
            # تحديث الإحصائيات العامة
            general_total_work_seconds += employee_total_work_seconds
            general_total_work_days += employee_work_days
            general_total_absent_days += employee_absent_days
        
        # حساب الإحصائيات العامة
        total_employees = len(accessible_employees)
        total_possible_days = total_employees * ((end_date - start_date).days + 1)
        attendance_rate = (general_total_work_days / total_possible_days * 100) if total_possible_days > 0 else 0
        avg_hours_per_employee_seconds = general_total_work_seconds / total_employees if total_employees > 0 else 0
        
        general_stats = {
            'total_employees': total_employees,
            'total_work_days': general_total_work_days,
            'total_absent_days': general_total_absent_days,
            'attendance_rate': attendance_rate,
            'total_work_hours': seconds_to_time_string(general_total_work_seconds),
            'avg_hours_per_employee': seconds_to_time_string(avg_hours_per_employee_seconds)
        }
        
        # إنشاء PDF
        pdf_buffer = create_general_report_pdf(start_date, end_date, employees_data, general_stats)
        
        # إرسال الملف
        filename = f"general_attendance_report_{start_date_str}_to_{end_date_str}.pdf"
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        print(f"Error generating general report: {str(e)}")
        return jsonify({'message': 'Error generating report', 'error': str(e)}), 500