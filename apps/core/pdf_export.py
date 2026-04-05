"""
تصدير التقارير بصيغة PDF
=========================
يستخدم ReportLab لإنشاء تقارير PDF احترافية باللغة العربية
"""

import io
from datetime import datetime
from decimal import Decimal

from django.http import HttpResponse

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph,
        Spacer,
    )
    from reportlab.lib.enums import TA_CENTER
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


def _reverse_arabic(text):
    """عكس النص العربي للعرض في PDF (حل بسيط بدون python-bidi)"""
    if not text:
        return ''
    return str(text)


def generate_pdf_response(filename, title, headers, data, landscape_mode=False):
    """
    إنشاء ملف PDF مع جدول بيانات

    Args:
        filename: اسم الملف
        title: عنوان التقرير
        headers: قائمة عناوين الأعمدة
        data: قائمة من القوائم (صفوف البيانات)
        landscape_mode: عرضي أو طولي
    """
    if not HAS_REPORTLAB:
        response = HttpResponse(content_type='text/plain; charset=utf-8')
        response.write('مكتبة reportlab غير مثبتة. قم بتشغيل: pip install reportlab')
        return response

    buffer = io.BytesIO()
    pagesize = landscape(A4) if landscape_mode else A4

    doc = SimpleDocTemplate(
        buffer,
        pagesize=pagesize,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    elements = []
    styles = getSampleStyleSheet()

    # عنوان التقرير
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=10 * mm,
    )
    elements.append(Paragraph(title, title_style))

    # التاريخ
    date_style = ParagraphStyle(
        'DateStyle',
        parent=styles['Normal'],
        fontSize=9,
        alignment=TA_CENTER,
        spaceAfter=8 * mm,
    )
    elements.append(Paragraph(
        f'Date: {datetime.now().strftime("%Y-%m-%d %H:%M")}',
        date_style
    ))

    # تجهيز البيانات مع العناوين
    table_data = [headers] + data

    # حساب عرض الأعمدة
    page_width = pagesize[0] - 30 * mm
    col_count = len(headers)
    col_width = page_width / col_count

    table = Table(table_data, colWidths=[col_width] * col_count)

    # تنسيق الجدول
    table_style = TableStyle([
        # رأس الجدول
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1d2e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

        # صفوف البيانات
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 6),

        # حدود
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),

        # ألوان الصفوف المتبادلة
        ('ROWBACKGROUNDS', (0, 1), (-1, -1),
         [colors.white, colors.HexColor('#f8f9fa')]),
    ])
    table.setStyle(table_style)

    elements.append(table)

    # عدد السجلات
    elements.append(Spacer(1, 5 * mm))
    count_style = ParagraphStyle(
        'CountStyle',
        parent=styles['Normal'],
        fontSize=9,
        alignment=TA_CENTER,
    )
    elements.append(Paragraph(
        f'Total Records: {len(data)}',
        count_style
    ))

    doc.build(elements)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def export_employees_pdf(modeladmin, request, queryset):
    """تصدير بيانات الموظفين إلى PDF"""
    headers = ['#', 'Employee Name', 'Number', 'National ID',
               'Branch', 'Department', 'Salary', 'Status']
    data = []
    for i, emp in enumerate(queryset, 1):
        data.append([
            str(i),
            str(emp.employee_name or ''),
            str(emp.employee_number or ''),
            str(emp.national_id or ''),
            str(emp.branch or ''),
            str(emp.department or ''),
            f'{emp.salary:,.2f}' if emp.salary else '0',
            str(emp.get_status_display()),
        ])
    return generate_pdf_response(
        'employees_report.pdf',
        'Employees Report',
        headers, data, landscape_mode=True
    )

export_employees_pdf.short_description = '📄 تصدير PDF - تقرير الموظفين'


def export_payroll_pdf(modeladmin, request, queryset):
    """تصدير كشف رواتب إلى PDF"""
    headers = ['#', 'Employee', 'Period', 'Basic Salary',
               'Allowances', 'Deductions', 'Net Salary', 'Status']
    data = []
    total_net = Decimal('0')
    for i, p in enumerate(queryset, 1):
        data.append([
            str(i),
            str(p.employee.employee_name if p.employee else ''),
            f'{p.period_month}/{p.period_year}',
            f'{p.basic_salary:,.2f}',
            f'{p.total_earnings - p.basic_salary:,.2f}',
            f'{p.total_deductions:,.2f}',
            f'{p.net_salary:,.2f}',
            str(p.get_status_display()),
        ])
        total_net += p.net_salary

    # صف الإجمالي
    data.append(['', '', '', '', '', 'Total:', f'{total_net:,.2f}', ''])

    return generate_pdf_response(
        'payroll_report.pdf',
        'Payroll Report',
        headers, data, landscape_mode=True
    )

export_payroll_pdf.short_description = '📄 تصدير PDF - كشف الرواتب'


def export_attendance_pdf(modeladmin, request, queryset):
    """تصدير سجلات الحضور إلى PDF"""
    headers = ['#', 'Employee', 'Branch', 'Date',
               'Shift Start', 'Shift End', 'Status']
    data = []
    for i, att in enumerate(queryset, 1):
        data.append([
            str(i),
            str(att.employee_name or ''),
            str(att.branch or ''),
            str(att.attendance_date or ''),
            str(att.shift_start or ''),
            str(att.shift_end or ''),
            str(att.get_status_display()),
        ])
    return generate_pdf_response(
        'attendance_report.pdf',
        'Attendance Report',
        headers, data, landscape_mode=True
    )

export_attendance_pdf.short_description = '📄 تصدير PDF - تقرير الحضور'


def export_performance_pdf(modeladmin, request, queryset):
    """تصدير تقييمات الأداء إلى PDF"""
    headers = ['#', 'Employee', 'Reviewer', 'Period',
               'Score', 'Rating', 'Acknowledged']
    data = []
    for i, pr in enumerate(queryset, 1):
        data.append([
            str(i),
            str(pr.employee.employee_name if pr.employee else ''),
            str(pr.reviewer.get_full_name() if pr.reviewer else ''),
            f'{pr.review_period_start} - {pr.review_period_end}',
            f'{pr.score}/5',
            str(pr.get_overall_rating_display()),
            'Yes' if pr.is_acknowledged else 'No',
        ])
    return generate_pdf_response(
        'performance_report.pdf',
        'Performance Reviews Report',
        headers, data, landscape_mode=True
    )

export_performance_pdf.short_description = '📄 تصدير PDF - تقرير الأداء'


def export_leaves_pdf(modeladmin, request, queryset):
    """تصدير طلبات الإجازات إلى PDF"""
    headers = ['#', 'Employee', 'Type', 'Days',
               'Start', 'End', 'Balance', 'Status']
    data = []
    for i, stmt in enumerate(queryset, 1):
        data.append([
            str(i),
            str(stmt.employee_name or ''),
            str(stmt.statement_type or ''),
            str(stmt.vacation_days or '0'),
            str(stmt.vacation_start or ''),
            str(stmt.vacation_end or ''),
            str(stmt.vacation_balance or '0'),
            str(stmt.get_status_display()),
        ])
    return generate_pdf_response(
        'leaves_report.pdf',
        'Leaves Report',
        headers, data, landscape_mode=True
    )

export_leaves_pdf.short_description = '📄 تصدير PDF - تقرير الإجازات'
