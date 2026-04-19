# app/recruitment/reports.py
# تصدير تقارير التوظيف - Excel و PDF

import io
import json
from datetime import datetime

from app.recruitment.models import (
    RecruitmentApplication,
    RecruitmentApplicationAnswer,
    RecruitmentFormSection,
    RecruitmentFormField,
    RecruitmentApplicationExperience,
)


# ─────────────────────────────────────────────────────────────────
# مساعدات مشتركة
# ─────────────────────────────────────────────────────────────────

def _get_ordered_fields():
    """
    إرجاع قائمة بكل الحقول النشطة مرتبة حسب القسم ثم display_order.
    تُستخدم لبناء أعمدة التقارير بشكل ديناميكي.
    """
    sections = (
        RecruitmentFormSection.query
        .filter_by(is_active=True)
        .order_by(RecruitmentFormSection.display_order)
        .all()
    )
    ordered_fields = []
    for section in sections:
        fields = (
            RecruitmentFormField.query
            .filter_by(section_id=section.id, is_active=True)
            .order_by(RecruitmentFormField.display_order)
            .all()
        )
        for field in fields:
            ordered_fields.append(field)
    return ordered_fields


def _get_applications(filters=None):
    """استرجاع الطلبات مع دعم الفلترة"""
    if filters is None:
        filters = {}

    query = RecruitmentApplication.query

    if filters.get('status'):
        query = query.filter(RecruitmentApplication.status == filters['status'])
    if filters.get('branch_id'):
        query = query.filter(RecruitmentApplication.branch_id == filters['branch_id'])
    if filters.get('department_id'):
        query = query.filter(RecruitmentApplication.department_id == filters['department_id'])
    if filters.get('date_from'):
        try:
            df = datetime.strptime(filters['date_from'], '%Y-%m-%d')
            query = query.filter(RecruitmentApplication.created_at >= df)
        except ValueError:
            pass
    if filters.get('date_to'):
        try:
            dt = datetime.strptime(filters['date_to'], '%Y-%m-%d')
            query = query.filter(RecruitmentApplication.created_at <= dt)
        except ValueError:
            pass

    return query.order_by(RecruitmentApplication.created_at.desc()).all()


def _build_answers_map(application_ids):
    """
    بناء قاموس { application_id: { field_id: value } }
    باستعلام واحد لكل الطلبات (تجنب N+1).
    """
    if not application_ids:
        return {}

    answers = (
        RecruitmentApplicationAnswer.query
        .filter(RecruitmentApplicationAnswer.application_id.in_(application_ids))
        .all()
    )
    result = {}
    for ans in answers:
        result.setdefault(ans.application_id, {})[ans.field_id] = ans.value
    return result


def _build_experiences_map(application_ids):
    """
    بناء قاموس { application_id: [experiences] }
    باستعلام واحد.
    """
    if not application_ids:
        return {}

    exps = (
        RecruitmentApplicationExperience.query
        .filter(RecruitmentApplicationExperience.application_id.in_(application_ids))
        .order_by(RecruitmentApplicationExperience.application_id,
                  RecruitmentApplicationExperience.experience_order)
        .all()
    )
    result = {}
    for exp in exps:
        result.setdefault(exp.application_id, []).append(exp)
    return result


STATUS_LABELS = {
    'new': 'جديد',
    'under_review': 'قيد المراجعة',
    'interview': 'مقابلة',
    'accepted': 'مقبول',
    'rejected': 'مرفوض',
}


# ─────────────────────────────────────────────────────────────────
# تصدير Excel
# ─────────────────────────────────────────────────────────────────

def export_excel(filters=None):
    """
    تصدير بيانات الطلبات إلى Excel.
    الأعمدة ديناميكية حسب الحقول النشطة.
    الخبرات مُفرَّدة: "خبرة 1 - الشركة", "خبرة 1 - الوظيفة"، إلخ.

    يعيد BytesIO object جاهز للإرسال كملف.
    """
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    except ImportError:
        raise RuntimeError("مكتبة openpyxl غير مثبتة")

    applications = _get_applications(filters)
    ordered_fields = _get_ordered_fields()

    app_ids = [a.id for a in applications]
    answers_map = _build_answers_map(app_ids)
    experiences_map = _build_experiences_map(app_ids)

    # تحديد الحد الأقصى لعدد الخبرات
    max_experiences = max(
        (len(exps) for exps in experiences_map.values()),
        default=0
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "طلبات التوظيف"
    ws.sheet_view.rightToLeft = True  # RTL

    # ───── بناء رأس الجدول ─────
    header_style = Font(bold=True, color="FFFFFF")
    fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    headers = ["#", "الحالة", "الفرع", "القسم", "تاريخ التقديم"]

    # إضافة أعمدة الحقول الديناميكية (ما عدا experience_group)
    dynamic_fields = [f for f in ordered_fields if f.field_type != 'experience_group']
    for field in dynamic_fields:
        headers.append(field.label)

    # إضافة أعمدة الخبرات المفرَّدة
    exp_sub_headers = ['الشركة', 'مجال الشركة', 'الوظيفة', 'مدة العمل', 'الساعات', 'المرتب', 'سبب الترك']
    for i in range(1, max_experiences + 1):
        for sub in exp_sub_headers:
            headers.append(f"خبرة {i} - {sub}")

    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num, value=header)
        cell.font = header_style
        cell.fill = fill
        cell.alignment = alignment

    ws.row_dimensions[1].height = 30

    # ───── بناء صفوف البيانات ─────
    for row_num, app in enumerate(applications, 2):
        ans = answers_map.get(app.id, {})
        exps = experiences_map.get(app.id, [])

        row_data = [
            app.id,
            STATUS_LABELS.get(app.status, app.status),
            app.branch.name if app.branch else '',
            app.department.name if app.department else '',
            app.created_at.strftime('%Y-%m-%d') if app.created_at else '',
        ]

        # قيم الحقول الديناميكية
        for field in dynamic_fields:
            row_data.append(ans.get(field.id, ''))

        # قيم الخبرات المفرَّدة
        for i in range(max_experiences):
            if i < len(exps):
                exp = exps[i]
                row_data.extend([
                    exp.company_name or '',
                    exp.company_field or '',
                    exp.position or '',
                    exp.duration or '',
                    exp.hours_per_day or '',
                    exp.salary or '',
                    exp.reason_for_leaving or '',
                ])
            else:
                row_data.extend(['', '', '', '', '', '', ''])

        for col_num, value in enumerate(row_data, 1):
            cell = ws.cell(row=row_num, column=col_num, value=value)
            cell.alignment = Alignment(horizontal="right", vertical="center", wrap_text=True)

    # ضبط عرض الأعمدة
    for col in ws.columns:
        max_len = max((len(str(cell.value or '')) for cell in col), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 40)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


# ─────────────────────────────────────────────────────────────────
# تصدير PDF
# ─────────────────────────────────────────────────────────────────

def export_pdf(filters=None):
    """
    تصدير بيانات الطلبات إلى PDF مع دعم RTL.
    يعيد BytesIO object جاهز للإرسال كملف.
    """
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        )
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import arabic_reshaper
        from bidi.algorithm import get_display
    except ImportError as e:
        raise RuntimeError(f"مكتبة مطلوبة غير مثبتة: {e}")

    # ──── محاولة تسجيل خط عربي ────
    import os
    fonts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'fonts')
    arabic_font = 'Helvetica'  # fallback
    for font_file in ['Amiri-Regular.ttf', 'Cairo-Regular.ttf', 'NotoSansArabic-Regular.ttf']:
        font_path = os.path.join(fonts_dir, font_file)
        if os.path.exists(font_path):
            font_name = font_file.replace('.ttf', '').replace('-Regular', '')
            pdfmetrics.registerFont(TTFont(font_name, font_path))
            arabic_font = font_name
            break

    def reshape(text):
        """تشكيل النص العربي للعرض الصحيح"""
        if not text:
            return ''
        try:
            reshaped = arabic_reshaper.reshape(str(text))
            return get_display(reshaped)
        except Exception:
            return str(text)

    applications = _get_applications(filters)
    ordered_fields = _get_ordered_fields()

    app_ids = [a.id for a in applications]
    answers_map = _build_answers_map(app_ids)

    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=1*cm, leftMargin=1*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm
    )

    styles = getSampleStyleSheet()
    arabic_style = ParagraphStyle(
        'Arabic',
        fontName=arabic_font,
        fontSize=9,
        leading=12,
        alignment=2,  # RIGHT
    )
    title_style = ParagraphStyle(
        'ArabicTitle',
        fontName=arabic_font,
        fontSize=14,
        leading=16,
        alignment=1,  # CENTER
        textColor=colors.HexColor('#1F4E79'),
    )

    story = []

    # عنوان التقرير
    story.append(Paragraph(reshape("تقرير طلبات التوظيف"), title_style))
    story.append(Paragraph(
        reshape(f"تاريخ الاستخراج: {datetime.now().strftime('%Y-%m-%d %H:%M')}"),
        arabic_style
    ))
    story.append(Spacer(1, 0.5*cm))

    # ──── أعمدة الجدول ────
    dynamic_fields = [f for f in ordered_fields if f.field_type != 'experience_group']
    # نقتصر على أهم الحقول لعدم تجاوز عرض الصفحة
    display_fields = dynamic_fields[:12]

    header_row = [reshape('#'), reshape('الحالة'), reshape('الفرع')]
    for field in display_fields:
        header_row.append(reshape(field.label))

    table_data = [header_row]

    for idx, app in enumerate(applications, 1):
        ans = answers_map.get(app.id, {})
        row = [
            str(idx),
            reshape(STATUS_LABELS.get(app.status, app.status)),
            reshape(app.branch.name if app.branch else ''),
        ]
        for field in display_fields:
            val = ans.get(field.id, '')
            row.append(reshape(str(val) if val else ''))
        table_data.append(row)

    col_widths = [1*cm, 2.5*cm, 2.5*cm] + [3*cm] * len(display_fields)

    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F4E79')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, -1), arabic_font),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#EBF3FB')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))

    story.append(table)
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        reshape(f"إجمالي الطلبات: {len(applications)}"),
        arabic_style
    ))

    doc.build(story)
    output.seek(0)
    return output
