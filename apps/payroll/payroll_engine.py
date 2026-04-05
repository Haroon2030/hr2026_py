"""
محرك توليد الرواتب
===================
يحسب رواتب الموظفين النشطين لفترة شهرية محددة
وفق نظام العمل السعودي ونظام التأمينات الاجتماعية.

قواعد الحساب:
─────────────────────────────────────────────────────
① تحديد أيام العمل الفعلية المستحقة (earned_days):
   • الشهر الماضي أو السابق:
       - إذا بدأ تعيينه في نفس الشهر  → من يوم التعيين حتى نهاية الشهر
       - إذا بدأ قبل هذا الشهر         → الشهر بالكامل
   • الشهر الجاري (today داخل الشهر):
       - إذا بدأ تعيينه في نفس الشهر  → من يوم التعيين حتى اليوم الحالي
       - إذا بدأ قبل هذا الشهر         → من أول الشهر حتى اليوم الحالي
   • الشهر المستقبلي (لم يبدأ بعد):
       - جميع الحقول = 0

② الراتب المستحق (gross):
   = (earned_days / days_in_month) × (راتب_أساسي + بدل_سكن + بدل_نقل + بدلات_أخرى)

③ الخصومات:
   - خصم الغياب    : سجلات AttendanceRecord بالشهر (يومي × عدد أيام الغياب)
   - خصم السلف     : مجموع AdvanceFile المعتمدة خلال الشهر
   - الخصومات الأخرى: حقل deductions في Payroll (يُدخله المستخدم يدوياً)
   - التأمينات     : سعودي 9 %، غير سعودي 0 %

④ صافي الراتب:
   = الإجمالي المستحق - إجمالي الخصومات
   (لا يقل عن صفر)
─────────────────────────────────────────────────────
"""
import calendar
from decimal import Decimal, ROUND_HALF_UP
from datetime import date

from django.db import models
from django.db.models import Sum
from django.utils import timezone

from .models import FinanceSettings

from apps.core.models import (
    EmployeeFile,
    AdvanceFile,
    AttendanceRecord,
    Payroll,
    PayrollStatusChoices,
    WorkerStatusLog,
)


# ══════════════════════════════════════════════════════════════
# دوال مساعدة
# ══════════════════════════════════════════════════════════════

def _is_saudi(nationality: str) -> bool:
    """تحديد ما إذا كان الموظف سعودياً."""
    n = (nationality or '').strip().lower()
    return 'سعود' in n or n in ('saudi', 'ksa')


def _earned_days(start_date: date, year: int, month: int, today: date) -> tuple[int, int, str]:
    """
    حساب أيام العمل الفعلية المستحقة للموظف في الشهر المحدد.

    المنطق:
    ┌─────────────────────────────────────────────────────────┐
    │ إذا كان الشهر مستقبلياً → 0 أيام                      │
    │ إذا كان الشهر ماضياً:                                   │
    │   • إذا بُدئ التعيين في هذا الشهر → من يوم التعيين      │
    │     حتى نهاية الشهر                                     │
    │   • وإلا → الشهر كامل                                   │
    │ إذا كان الشهر الحالي:                                   │
    │   • يوم البداية = max(1, start_date.day)                │
    │   • يوم النهاية = today.day                              │
    │   (مع ضمان أن start_date ≤ today)                       │
    └─────────────────────────────────────────────────────────┘

    يُعيد: (earned_days, days_in_month, note)
    """
    days_in_month = calendar.monthrange(year, month)[1]
    period_start  = date(year, month, 1)
    period_end    = date(year, month, days_in_month)

    # ── شهر مستقبلي ─────────────────────────────────────────
    if period_start > today:
        return 0, days_in_month, "شهر مستقبلي - لم يبدأ بعد"

    # ── تاريخ تعيين الموظف: بداية الحساب ─────────────────
    if start_date and start_date.year == year and start_date.month == month:
        # تعيين في نفس الشهر
        work_start = start_date.day
    else:
        # تعيين قبل هذا الشهر → يبدأ من أول الشهر
        work_start = 1

    # ── تحديد نهاية الفترة ───────────────────────────────
    if year == today.year and month == today.month:
        # الشهر الجاري → حتى اليوم الحالي
        work_end = today.day
        note = f"شهر جاري: من {work_start} إلى {work_end} من {days_in_month} يوم"
    else:
        # شهر ماضٍ → حتى نهاية الشهر
        work_end = days_in_month
        note = None  # شهر كامل أو جزئي بسبب تاريخ التعيين فقط
        if work_start > 1:
            note = f"موظف جديد: تعيين يوم {work_start} - مستحق {days_in_month - work_start + 1} يوم"

    # ── تأكد أن work_start ≤ work_end ───────────────────
    if work_start > work_end:
        return 0, days_in_month, "لم تبدأ أيام العمل بعد"

    earned = work_end - work_start + 1
    return earned, days_in_month, note


def _absence_deduction(employee_name: str, year: int, month: int, daily_rate: Decimal) -> tuple:
    """
    حساب خصم الغياب بناءً على سجلات الحضور (AttendanceRecord).
    """
    if not employee_name or daily_rate <= 0:
        return Decimal('0'), 0

    absence_days = AttendanceRecord.objects.filter(
        employee_name=employee_name,
        attendance_date__year=year,
        attendance_date__month=month,
        status='approved',
    ).count()

    if absence_days <= 0:
        return Decimal('0'), 0

    # الخصم = اليومي * عدد الأيام (مع ضمان عدم تجاوز أيام الشهر)
    days_in_month = calendar.monthrange(year, month)[1]
    absence_days = min(absence_days, days_in_month)
    deduction = (daily_rate * Decimal(absence_days)).quantize(Decimal('0.01'), ROUND_HALF_UP)
    return deduction, absence_days


def _advance_deduction(employee_number: str, year: int, month: int) -> Decimal:
    """
    مجموع السلف المعتمدة للموظف خلال الشهر المحدد.

    يبحث أولاً في advance_date ثم في created_at كاحتياط.
    """
    if not employee_number:
        return Decimal('0')

    # بحث بتاريخ السلفة أولاً
    qs = AdvanceFile.objects.filter(
        employee_number=employee_number,
        manager_approval='approved',
        advance_date__year=year,
        advance_date__month=month,
    )

    if not qs.exists():
        # احتياط: بحث بتاريخ الإنشاء
        qs = AdvanceFile.objects.filter(
            employee_number=employee_number,
            manager_approval='approved',
            created_at__year=year,
            created_at__month=month,
        )

    total = qs.aggregate(s=Sum('advance_amount'))['s']
    return Decimal(str(total or 0))


def _status_excluded_days(employee, year: int, month: int) -> tuple[int, int, str]:
    """
    حساب أيام الإيقاف والإجازة المستبعدة من الراتب.
    
    يُستخدم WorkerStatusLog لحساب عدد الأيام التي يكون فيها الموظف:
    - موقوف (suspended)
    - في إجازة (leave)
    
    Returns:
        (suspended_days, leave_days, note)
    """
    days_in_month = calendar.monthrange(year, month)[1]
    period_start = date(year, month, 1)
    period_end = date(year, month, days_in_month)
    
    suspended_days = 0
    leave_days = 0
    
    # جلب سجلات الحالة النشطة أو التي تتقاطع مع الشهر
    status_logs = WorkerStatusLog.objects.filter(
        employee=employee,
        start_date__lte=period_end,
    ).filter(
        # إما نشطة أو انتهت بعد بداية الشهر
        models.Q(is_active=True) | models.Q(end_date__gte=period_start)
    )
    
    for log in status_logs:
        days = log.get_excluded_days(period_start, period_end)
        if log.status_type == 'suspended':
            suspended_days += days
        elif log.status_type == 'leave':
            leave_days += days
    
    notes = []
    if suspended_days > 0:
        notes.append(f"موقوف: {suspended_days} يوم")
    if leave_days > 0:
        notes.append(f"إجازة: {leave_days} يوم")
    
    return suspended_days, leave_days, ' | '.join(notes)


# ══════════════════════════════════════════════════════════════
# الدالة الرئيسية
# ══════════════════════════════════════════════════════════════

def generate_payroll(period, user) -> dict:
    """
    توليد كشوف رواتب لجميع الموظفين النشطين لفترة محددة.

    الخطوات:
    1. جلب إعدادات التأمينات الاجتماعية.
    2. جلب الموظفين النشطين الذين بدأ تعيينهم قبل نهاية الشهر.
    3. لكل موظف:
       a. حساب أيام العمل الفعلية (earndays_days).
       b. حساب الإجمالي المستحق تناسبياً (راتب + بدلات).
       c. حساب خصم الغياب.
       d. جلب مجموع السلف.
       e. حساب التأمينات على الإجمالي المستحق.
       f. حساب الصافي = إجمالي - خصومات.
    4. تحديث إحصائيات الفترة.
    """
    month      = period.month
    year       = period.year
    today      = date.today()
    last_day   = date(year, month, calendar.monthrange(year, month)[1])
    TWO_PLACES = Decimal('0.01')

    # ── إعدادات التأمينات ────────────────────────────────────
    finance_settings = FinanceSettings.load()
    saudi_ins_rate   = finance_settings.saudi_social_insurance_rate

    # ── الموظفون النشطون ─────────────────────────────────────
    active_emps = EmployeeFile.objects.filter(
        manager_approval='approved',
        start_date__isnull=False,
        start_date__lte=last_day,
    ).select_related('branch').order_by('employee_name')

    created     = 0
    skipped     = 0
    total_basic = Decimal('0')
    total_net   = Decimal('0')

    for emp in active_emps:

        # ── تخطي إذا يوجد كشف راتب مسبقاً ─────────────────
        if Payroll.objects.filter(
            employee=emp, period_month=month, period_year=year
        ).exists():
            skipped += 1
            continue

        # ── الراتب والبدلات من ملف الموظف ──────────────────
        basic_full     = (emp.salary              or Decimal('0')).quantize(TWO_PLACES)
        housing_full   = (getattr(emp, 'housing_allowance',   Decimal('0')) or Decimal('0')).quantize(TWO_PLACES)
        transport_full = (getattr(emp, 'transport_allowance', Decimal('0')) or Decimal('0')).quantize(TWO_PLACES)
        other_full     = (getattr(emp, 'other_allowances',    Decimal('0')) or Decimal('0')).quantize(TWO_PLACES)
        total_full     = basic_full + housing_full + transport_full + other_full

        if basic_full <= 0:
            skipped += 1
            continue

        # ── حساب أيام العمل ──────────────────────────────────
        earned, days_in_month, note = _earned_days(emp.start_date, year, month, today)

        notes_parts = []
        if note:
            notes_parts.append(note)

        # ── حساب أيام الإيقاف والإجازة المستبعدة ──────────────
        suspended_days, leave_days, status_note = _status_excluded_days(emp, year, month)
        excluded_days = suspended_days + leave_days
        if status_note:
            notes_parts.append(status_note)
        
        # طرح أيام الإيقاف/الإجازة من الأيام المستحقة
        earned = max(0, earned - excluded_days)

        # ── إذا صفر أيام: كشف بأصفار ────────────────────────
        if earned == 0:
            payroll = Payroll(
                employee            = emp,
                period_month        = month,
                period_year         = year,
                basic_salary        = Decimal('0'),
                housing_allowance   = Decimal('0'),
                transport_allowance = Decimal('0'),
                other_allowances    = Decimal('0'),
                social_insurance    = Decimal('0'),
                absence_deduction   = Decimal('0'),
                advance_deduction   = Decimal('0'),
                deductions          = Decimal('0'),
                status              = PayrollStatusChoices.DRAFT,
                created_by          = user,
                notes               = ' | '.join(notes_parts) or None,
            )
            payroll.save()
            created += 1
            continue

        # ── الحساب التناسبي ──────────────────────────────────
        ratio = Decimal(earned) / Decimal(days_in_month)

        basic_adj     = (basic_full     * ratio).quantize(TWO_PLACES, ROUND_HALF_UP)
        housing_adj   = (housing_full   * ratio).quantize(TWO_PLACES, ROUND_HALF_UP)
        transport_adj = (transport_full * ratio).quantize(TWO_PLACES, ROUND_HALF_UP)
        other_adj     = (other_full     * ratio).quantize(TWO_PLACES, ROUND_HALF_UP)
        gross_adj     = basic_adj + housing_adj + transport_adj + other_adj

        # ── التأمينات الاجتماعية (على الإجمالي المستحق) ─────
        if _is_saudi(getattr(emp, 'nationality', '')):
            social_ins = (gross_adj * saudi_ins_rate).quantize(TWO_PLACES, ROUND_HALF_UP)
        else:
            social_ins = Decimal('0')

        # ── خصم الغياب ──────────────────────────────────────
        daily_rate = (total_full / Decimal(days_in_month)).quantize(TWO_PLACES, ROUND_HALF_UP)
        absence_ded, absence_days = _absence_deduction(
            emp.employee_name, year, month, daily_rate
        )
        if absence_days > 0:
            notes_parts.append(f"غياب: {absence_days} يوم")

        # ── خصم السلف ────────────────────────────────────────
        advance_amt = _advance_deduction(
            getattr(emp, 'employee_number', None), year, month
        )
        if advance_amt > 0:
            notes_parts.append(f"سلفة: {advance_amt:,.2f}")

        # ── جلب القسم (department) ككائن إن وجد ────────────
        from apps.core.models import DepartmentModel
        emp_dept_name = getattr(emp, 'department', None)
        dept_obj = None
        if emp_dept_name:
            dept_obj = DepartmentModel.objects.filter(name=emp_dept_name).first()

        # ── إنشاء الكشف ──────────────────────────────────────
        payroll = Payroll(
            employee            = emp,
            department          = dept_obj,
            period_month        = month,
            period_year         = year,
            basic_salary        = basic_adj,
            housing_allowance   = housing_adj,
            transport_allowance = transport_adj,
            other_allowances    = other_adj,
            social_insurance    = social_ins,
            absence_deduction   = absence_ded,
            advance_deduction   = advance_amt,
            deductions          = Decimal('0'),
            status              = PayrollStatusChoices.DRAFT,
            created_by          = user,
            notes               = ' | '.join(notes_parts) or None,
        )
        payroll.save()   # يُشغّل calculate_net_salary() تلقائياً ويضمن تقريب النتائج

        created     += 1
        total_basic += basic_adj
        total_net   += payroll.net_salary

    # ── تحديث إحصائيات الفترة ────────────────────────────────
    period.generated_employees = created
    period.skipped_employees   = skipped
    period.total_basic         = total_basic
    period.total_net           = total_net
    period.generated_by        = user
    period.generated_at        = timezone.now()
    if period.status == 'open':
        period.status = 'generated'
    period.save()

    return {
        'created':     created,
        'skipped':     skipped,
        'total_basic': total_basic,
        'total_net':   total_net,
    }
