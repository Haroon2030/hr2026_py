"""
توليد ملف PDF لكشف الرواتب الشهري
====================================
يُنشئ ملفاً واحداً يحتوي على رواتب جميع الموظفين للفترة المحددة.
يستخدم ReportLab.
"""
import io
from datetime import datetime
from decimal import Decimal

from django.http import HttpResponse

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer, HRFlowable,
)

# ── ثوابت الألوان ──────────────────────────────
CLR_HEADER_BG  = colors.HexColor('#1a1d2e')
CLR_HEADER_FG  = colors.whitesmoke
CLR_SUB_BG     = colors.HexColor('#f0f4ff')
CLR_ALT        = colors.HexColor('#f8f9fa')
CLR_TOTAL_BG   = colors.HexColor('#28a745')
CLR_TOTAL_FG   = colors.white
CLR_BORDER     = colors.HexColor('#dee2e6')
CLR_GREEN      = colors.HexColor('#28a745')
CLR_RED        = colors.HexColor('#dc3545')

_MONTHS_AR = {
    1:'يناير', 2:'فبراير', 3:'مارس', 4:'أبريل',
    5:'مايو',  6:'يونيو',  7:'يوليو', 8:'أغسطس',
    9:'سبتمبر', 10:'أكتوبر', 11:'نوفمبر', 12:'ديسمبر',
}


def _fmt(value):
    """تنسيق رقم مالي."""
    try:
        return f"{Decimal(str(value)):,.2f}"
    except Exception:
        return str(value or '0.00')


def export_payroll_pdf(payrolls, period):
    """
    إنشاء HttpResponse يحتوي على PDF كشف الرواتب.

    payrolls : QuerySet أو list من Payroll
    period   : PayrollPeriod أو أي كائن له month و year
    """
    buffer    = io.BytesIO()
    page_size = landscape(A4)

    doc = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles  = getSampleStyleSheet()
    story   = []

    # ═══════════════════════════════════════════
    # رأس الصفحة
    # ═══════════════════════════════════════════
    title_style = ParagraphStyle(
        'HRTitle',
        fontSize=18, fontName='Helvetica-Bold',
        alignment=TA_CENTER, textColor=CLR_HEADER_BG,
        spaceAfter=2 * mm,
    )
    sub_style = ParagraphStyle(
        'HRSub',
        fontSize=11, fontName='Helvetica',
        alignment=TA_CENTER, textColor=colors.HexColor('#6c757d'),
        spaceAfter=1 * mm,
    )
    story.append(Paragraph('Payroll Report', title_style))

    month_label = _MONTHS_AR.get(period.month, period.month)
    story.append(Paragraph(
        f"Period: {month_label} {period.year}  |  "
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        sub_style,
    ))
    story.append(HRFlowable(width='100%', thickness=1, color=CLR_BORDER, spaceAfter=5 * mm))

    # ═══════════════════════════════════════════
    # جدول الرواتب
    # ═══════════════════════════════════════════
    headers = [
        '#',
        'Employee Name',
        'Emp No.',
        'Branch',
        'Basic',
        'Housing',
        'Transport',
        'Other',
        'Overtime',
        'Ins.',
        'Absence',
        'Advance',
        'Deduct.',
        'NET',
        'Status',
    ]

    rows   = []
    totals = {
        'basic': Decimal('0'), 'housing': Decimal('0'),
        'transport': Decimal('0'), 'other': Decimal('0'),
        'overtime': Decimal('0'), 'ins': Decimal('0'),
        'absence': Decimal('0'), 'advance': Decimal('0'),
        'deductions': Decimal('0'), 'net': Decimal('0'),
    }

    STATUS_MAP = {
        'draft':    'Draft',
        'pending':  'Pending',
        'approved': 'Approved',
        'paid':     'Paid',
        'cancelled':'Cancelled',
    }

    for i, p in enumerate(payrolls, 1):
        rows.append([
            str(i),
            str(p.employee.employee_name if p.employee else ''),
            str(p.employee.employee_number if p.employee else ''),
            str(p.employee.branch or ''),
            _fmt(p.basic_salary),
            _fmt(p.housing_allowance),
            _fmt(p.transport_allowance),
            _fmt(p.other_allowances),
            _fmt(p.overtime_amount),
            _fmt(p.social_insurance),
            _fmt(p.absence_deduction),
            _fmt(p.advance_deduction),
            _fmt(p.deductions),
            _fmt(p.net_salary),
            STATUS_MAP.get(p.status, p.status),
        ])
        totals['basic']      += (p.basic_salary      or Decimal('0'))
        totals['housing']    += (p.housing_allowance  or Decimal('0'))
        totals['transport']  += (p.transport_allowance or Decimal('0'))
        totals['other']      += (p.other_allowances   or Decimal('0'))
        totals['overtime']   += (p.overtime_amount    or Decimal('0'))
        totals['ins']        += (p.social_insurance   or Decimal('0'))
        totals['absence']    += (p.absence_deduction  or Decimal('0'))
        totals['advance']    += (p.advance_deduction  or Decimal('0'))
        totals['deductions'] += (p.deductions         or Decimal('0'))
        totals['net']        += (p.net_salary         or Decimal('0'))

    # صف المجاميع
    rows.append([
        '', 'TOTAL', '', '',
        _fmt(totals['basic']),
        _fmt(totals['housing']),
        _fmt(totals['transport']),
        _fmt(totals['other']),
        _fmt(totals['overtime']),
        _fmt(totals['ins']),
        _fmt(totals['absence']),
        _fmt(totals['advance']),
        _fmt(totals['deductions']),
        _fmt(totals['net']),
        '',
    ])

    table_data = [headers] + rows

    # أعراض الأعمدة (mm)
    pw = page_size[0] - 24 * mm
    col_widths = [
        8*mm,   # #
        38*mm,  # name
        18*mm,  # emp no
        22*mm,  # branch
        22*mm,  # basic
        18*mm,  # housing
        18*mm,  # transport
        15*mm,  # other
        18*mm,  # overtime
        16*mm,  # ins
        16*mm,  # absence
        16*mm,  # advance
        16*mm,  # deductions
        22*mm,  # net
        18*mm,  # status
    ]

    total_row = len(rows)   # index of totals row (1-based in platypus = total_row + 1)

    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        # ── رأس الجدول ─────────────────────────
        ('BACKGROUND',   (0, 0), (-1, 0),  CLR_HEADER_BG),
        ('TEXTCOLOR',    (0, 0), (-1, 0),  CLR_HEADER_FG),
        ('FONTNAME',     (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',     (0, 0), (-1, 0),  8),
        ('ALIGN',        (0, 0), (-1, 0),  'CENTER'),
        ('BOTTOMPADDING',(0, 0), (-1, 0),  6),
        ('TOPPADDING',   (0, 0), (-1, 0),  6),

        # ── صفوف البيانات ───────────────────────
        ('FONTSIZE',     (0, 1), (-1, -2), 8),
        ('ALIGN',        (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING',(0, 1), (-1, -2), 5),
        ('TOPPADDING',   (0, 1), (-1, -2), 5),
        ('ROWBACKGROUNDS',(0, 1), (-1, -2),
         [colors.white, CLR_ALT]),

        # ── صف المجاميع ─────────────────────────
        ('BACKGROUND',   (0, -1), (-1, -1), CLR_TOTAL_BG),
        ('TEXTCOLOR',    (0, -1), (-1, -1), CLR_TOTAL_FG),
        ('FONTNAME',     (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE',     (0, -1), (-1, -1), 9),
        ('BOTTOMPADDING',(0, -1), (-1, -1), 7),
        ('TOPPADDING',   (0, -1), (-1, -1), 7),

        # ── حدود ────────────────────────────────
        ('GRID',         (0, 0), (-1, -1), 0.4, CLR_BORDER),
        ('LINEBELOW',    (0, 0), (-1, 0),  1.2, CLR_HEADER_BG),
    ]))

    story.append(tbl)

    # ═══════════════════════════════════════════
    # ملخص ختامي
    # ═══════════════════════════════════════════
    story.append(Spacer(1, 8 * mm))
    summary_data = [
        ['Employees', str(len(payrolls)),
         'Total Basic', _fmt(totals['basic']),
         'Total Net', _fmt(totals['net'])],
        ['Total Insurance', _fmt(totals['ins']),
         'Total Deductions',
         _fmt(totals['ins'] + totals['absence'] + totals['advance'] + totals['deductions']),
         'Paid', str(sum(1 for p in payrolls if p.status == 'paid'))],
    ]
    summary_tbl = Table(summary_data, colWidths=[35*mm, 28*mm, 38*mm, 30*mm, 28*mm, 30*mm])
    summary_tbl.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, -1), CLR_SUB_BG),
        ('FONTNAME',     (0, 0), (-2, -1), 'Helvetica-Bold'),
        ('FONTSIZE',     (0, 0), (-1, -1), 9),
        ('ALIGN',        (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID',         (0, 0), (-1, -1), 0.5, CLR_BORDER),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 6),
        ('TOPPADDING',   (0, 0), (-1, -1), 6),
        ('TEXTCOLOR',    (5, 0), (5, 0),   CLR_GREEN),
    ]))
    story.append(summary_tbl)

    doc.build(story)
    buffer.seek(0)

    filename = f"payroll_{period.year}_{period.month:02d}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
