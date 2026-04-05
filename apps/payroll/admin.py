"""
إدارة قسم المالية
==================
PayrollPeriodAdmin : إدارة فترات الرواتب + زر توليد الشهر الحالي
PayrollProxyAdmin  : عرض وتعديل كشوف الرواتب الفردية
"""
import datetime

from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect, render
from django.utils.html import format_html
from django.utils import timezone
from django.contrib import messages
from rangefilter.filters import DateRangeFilter

from .excel_payroll import export_payroll_excel

from apps.core.models import Payroll, PayrollStatusChoices
from apps.core.admin.payroll import PayrollAdmin as BasePayrollAdmin

from .models import PayrollPeriod, PayrollProxy, PeriodStatus, FinanceSettings
from .payroll_engine import generate_payroll

_MONTHS_AR = {
    1:'يناير', 2:'فبراير', 3:'مارس', 4:'أبريل',
    5:'مايو',  6:'يونيو',  7:'يوليو', 8:'أغسطس',
    9:'سبتمبر', 10:'أكتوبر', 11:'نوفمبر', 12:'ديسمبر',
}

def _month_label(month, year):
    return f"{_MONTHS_AR.get(month, month)} {year}"


# ══════════════════════════════════════════════
#  فترات الرواتب
# ══════════════════════════════════════════════

@admin.register(PayrollPeriod)
class PayrollPeriodAdmin(admin.ModelAdmin):
    """
    إدارة فترات الرواتب الشهرية.
    زر "توليد رواتب الشهر الحالي" يُنشئ الفترة تلقائياً
    ويولّد رواتب جميع الموظفين النشطين بضغطة واحدة.
    """

    change_list_template = 'admin/payroll/payrollperiod/change_list.html'

    list_display = (
        'period_label', 'status_badge',
        'generated_employees', 'skipped_employees',
        'total_basic_display', 'total_net_display',
        'generated_by', 'generated_at_display',
    )
    list_filter  = ('status', 'year')
    search_fields = ('notes',)
    readonly_fields = (
        'generated_employees', 'skipped_employees',
        'total_basic', 'total_net', 'excel_file',
        'generated_by', 'generated_at',
        'approved_by', 'approved_at',
        'paid_at', 'created_at', 'updated_at',
    )
    ordering = ('-year', '-month')

    fieldsets = (
        ('تحديد الفترة', {
            'fields': ('month', 'year', 'status', 'notes'),
            'classes': ('tab',),
        }),
        ('إحصائيات التوليد', {
            'fields': (
                'generated_employees', 'skipped_employees',
                'total_basic', 'total_net', 'excel_file',
            ),
            'classes': ('tab',),
        }),
        ('سجل العمليات', {
            'fields': (
                'generated_by', 'generated_at',
                'approved_by', 'approved_at',
                'paid_at', 'created_at', 'updated_at',
            ),
            'classes': ('tab',),
        }),
    )

    actions = [
        'action_generate_payroll',
        'action_approve_period',
        'action_mark_paid',
        'action_close_period',
    ]

    # ── URL مخصص لزر التوليد الفوري ───────────

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                'generate-form/',
                self.admin_site.admin_view(self.generate_form_view),
                name='payroll_generate_form',
            ),
        ]
        return custom + urls

    def generate_form_view(self, request):
        """
        GET  → عرض نموذج اختيار الشهر والسنة
        POST → توليد الرواتب وإرجاع ملف PDF
        """
        today = datetime.date.today()

        if request.method == 'POST':
            try:
                month = int(request.POST.get('month', today.month))
                year  = int(request.POST.get('year',  today.year))
                if not (1 <= month <= 12 and 2000 <= year <= 2100):
                    raise ValueError
            except (ValueError, TypeError):
                self.message_user(request, 'تاريخ غير صالح.', level=messages.ERROR)
                return redirect('.')

            # ── منع توليد رواتب لشهر مستقبلي ─────────────────
            if (year, month) > (today.year, today.month):
                self.message_user(
                    request,
                    f'لا يمكن توليد رواتب لشهر مستقبلي '
                    f'({month}/{year}). نحن الآن في {today.month}/{today.year}.',
                    level=messages.ERROR,
                )
                return redirect('.')

            period, _ = PayrollPeriod.objects.get_or_create(
                month=month, year=year,
                defaults={'status': PeriodStatus.OPEN},
            )

            if period.status == PeriodStatus.CLOSED:
                self.message_user(
                    request,
                    f'الفترة {period} مغلقة. لا يمكن إعادة التوليد.',
                    level=messages.WARNING,
                )
                return redirect('../')

            generate_payroll(period, request.user)

            from apps.core.models import Payroll
            payrolls = Payroll.objects.filter(
                period_month=month, period_year=year
            ).select_related('employee').order_by('employee__employee_name')

            return export_payroll_excel(payrolls, period)

        # GET – عرض النموذج
        context = {
            **self.admin_site.each_context(request),
            'title': 'توليد كشف رواتب',
            'months': [
                (1,'يناير'),(2,'فبراير'),(3,'مارس'),(4,'أبريل'),
                (5,'مايو'),(6,'يونيو'),(7,'يوليو'),(8,'أغسطس'),
                (9,'سبتمبر'),(10,'أكتوبر'),(11,'نوفمبر'),(12,'ديسمبر'),
            ],
            'current_month': today.month,
            'current_year':  today.year,
            'opts': self.model._meta,
        }
        return render(request, 'admin/payroll/payrollperiod/generate_form.html', context)

    def changelist_view(self, request, extra_context=None):
        today = datetime.date.today()
        extra_context = extra_context or {}
        extra_context['current_month_label'] = _month_label(today.month, today.year)
        return super().changelist_view(request, extra_context=extra_context)

    # ── عرض الخلايا ───────────────────────────

    @admin.display(description='الفترة', ordering='-year')
    def period_label(self, obj):
        return format_html('<strong>{}</strong>', obj.month_label)

    @admin.display(description='الحالة')
    def status_badge(self, obj):
        colors = {
            'open':      ('#6c757d', 'مفتوحة'),
            'generated': ('#17a2b8', 'تم التوليد'),
            'approved':  ('#28a745', 'معتمدة'),
            'paid':      ('#007bff', 'تم الصرف'),
            'closed':    ('#343a40', 'مغلقة'),
        }
        color, label = colors.get(obj.status, ('#6c757d', obj.status))
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 10px;'
            'border-radius:10px;font-size:11px;">{}</span>',
            color, label
        )

    @admin.display(description='إجمالي الأساسي')
    def total_basic_display(self, obj):
        if obj.total_basic:
            return format_html('<span style="font-weight:700;">{}</span>', f'{obj.total_basic:,.2f}')
        return '–'

    @admin.display(description='إجمالي الصافي')
    def total_net_display(self, obj):
        if obj.total_net:
            return format_html(
                '<span style="font-weight:700;color:#28a745;">{}</span>',
                f'{obj.total_net:,.2f}',
            )
        return '–'

    @admin.display(description='تاريخ التوليد')
    def generated_at_display(self, obj):
        if obj.generated_at:
            return obj.generated_at.strftime('%Y-%m-%d %H:%M')
        return '–'

    # ── الإجراءات (Actions) ────────────────────

    @admin.action(description='⚙ توليد رواتب الفترة المحددة')
    def action_generate_payroll(self, request, queryset):
        today = datetime.date.today()
        for period in queryset:
            if period.status == PeriodStatus.CLOSED:
                self.message_user(
                    request,
                    f'الفترة {period} مغلقة ولا يمكن إعادة توليدها.',
                    level=messages.WARNING,
                )
                continue
            # ── منع توليد رواتب لشهر مستقبلي ─────────────────
            if (period.year, period.month) > (today.year, today.month):
                self.message_user(
                    request,
                    f'الفترة {period} مستقبلية. لا يمكن توليد رواتب قبل بدء الشهر.',
                    level=messages.ERROR,
                )
                continue
            result = generate_payroll(period, request.user)
            self.message_user(
                request,
                f'✅ {period}: تم توليد {result["created"]} كشف راتب'
                f' (تخطي: {result["skipped"]}) | '
                f'صافي إجمالي: {result["total_net"]:,.2f} ريال',
                level=messages.SUCCESS,
            )

    @admin.action(description='✔ اعتماد الفترة المحددة')
    def action_approve_period(self, request, queryset):
        updated = queryset.filter(
            status__in=[PeriodStatus.GENERATED, PeriodStatus.OPEN]
        ).update(
            status=PeriodStatus.APPROVED,
            approved_by=request.user,
            approved_at=timezone.now(),
        )
        # اعتماد كشوف الرواتب المرتبطة أيضاً
        for period in queryset:
            Payroll.objects.filter(
                period_month=period.month,
                period_year=period.year,
                status=PayrollStatusChoices.DRAFT,
            ).update(
                status=PayrollStatusChoices.APPROVED,
                approved_by=request.user,
                approved_at=timezone.now(),
            )
        self.message_user(request, f'تم اعتماد {updated} فترة.', level=messages.SUCCESS)

    @admin.action(description='💰 تعليم الفترة كمصروفة')
    def action_mark_paid(self, request, queryset):
        now = timezone.now()
        updated = queryset.filter(status=PeriodStatus.APPROVED).update(
            status=PeriodStatus.PAID,
            paid_at=now,
        )
        for period in queryset:
            Payroll.objects.filter(
                period_month=period.month,
                period_year=period.year,
                status=PayrollStatusChoices.APPROVED,
            ).update(status=PayrollStatusChoices.PAID, paid_at=now)
        self.message_user(request, f'تم تعليم {updated} فترة كمصروفة.', level=messages.SUCCESS)

    @admin.action(description='🔒 إغلاق الفترة')
    def action_close_period(self, request, queryset):
        updated = queryset.update(status=PeriodStatus.CLOSED)
        self.message_user(request, f'تم إغلاق {updated} فترة.', level=messages.SUCCESS)


# ══════════════════════════════════════════════
#  كشوف الرواتب (Proxy)
# ══════════════════════════════════════════════

@admin.register(PayrollProxy)
class PayrollProxyAdmin(BasePayrollAdmin):
    """
    عرض وتعديل كشوف الرواتب الفردية.
    يرث كل وظائف PayrollAdmin الأصلية مع إضافات مالية.
    """

    list_display = (
        'employee', 'period_display',
        'basic_salary_display',
        'total_earnings_display',
        'total_deductions_display',
        'net_salary_display',
        'status_badge', 'created_at',
    )
    list_filter = (
        'status',
        'period_year',
        'period_month',
        'department',
        ('created_at', DateRangeFilter),
    )
    search_fields = (
        'employee__employee_name',
        'employee__employee_number',
        'employee__branch',
        'notes',
    )
    ordering = ('-period_year', '-period_month', 'employee__employee_name')
    readonly_fields = (
        'net_salary', 'approved_by', 'approved_at',
        'paid_at', 'created_by', 'created_at', 'updated_at',
    )
    list_per_page = 30
    actions = [
        'action_approve_payrolls',
        'action_mark_paid',
        'action_reset_to_draft',
    ]

    # ── عرض الخلايا ───────────────────────────

    @admin.display(description='الفترة', ordering='period_year')
    def period_display(self, obj):
        months_ar = {
            1:'يناير', 2:'فبراير', 3:'مارس', 4:'أبريل',
            5:'مايو',  6:'يونيو',  7:'يوليو', 8:'أغسطس',
            9:'سبتمبر', 10:'أكتوبر', 11:'نوفمبر', 12:'ديسمبر',
        }
        return f"{months_ar.get(obj.period_month, obj.period_month)} {obj.period_year}"

    @admin.display(description='الأساسي', ordering='basic_salary')
    def basic_salary_display(self, obj):
        return format_html('<span>{}</span>', f'{obj.basic_salary:,.2f}')

    @admin.display(description='الإجمالي')
    def total_earnings_display(self, obj):
        return format_html(
            '<span style="color:#007bff;font-weight:600;">{}</span>',
            f'{obj.total_earnings:,.2f}',
        )

    @admin.display(description='الخصومات')
    def total_deductions_display(self, obj):
        return format_html(
            '<span style="color:#dc3545;">{}</span>',
            f'{obj.total_deductions:,.2f}',
        )

    @admin.display(description='الصافي', ordering='net_salary')
    def net_salary_display(self, obj):
        return format_html(
            '<span style="font-weight:700;color:#28a745;">{}</span>',
            f'{obj.net_salary:,.2f}',
        )

    @admin.display(description='الحالة')
    def status_badge(self, obj):
        colors = {
            'draft':    ('#6c757d', 'مسودة'),
            'pending':  ('#ffc107', 'بانتظار الاعتماد'),
            'approved': ('#28a745', 'معتمد'),
            'paid':     ('#007bff', 'مصروف'),
            'cancelled':('#dc3545', 'ملغي'),
        }
        color, label = colors.get(obj.status, ('#6c757d', obj.status))
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;'
            'border-radius:10px;font-size:11px;">{}</span>',
            color, label
        )

    # ── الإجراءات (Actions) ────────────────────

    @admin.action(description='✔ اعتماد الكشوف المحددة')
    def action_approve_payrolls(self, request, queryset):
        now = timezone.now()
        updated = queryset.filter(
            status__in=[PayrollStatusChoices.DRAFT, PayrollStatusChoices.PENDING]
        ).update(
            status=PayrollStatusChoices.APPROVED,
            approved_by=request.user,
            approved_at=now,
        )
        self.message_user(request, f'تم اعتماد {updated} كشف راتب.', level=messages.SUCCESS)

    @admin.action(description='💰 تعليم كمصروف')
    def action_mark_paid(self, request, queryset):
        now = timezone.now()
        updated = queryset.filter(
            status=PayrollStatusChoices.APPROVED
        ).update(
            status=PayrollStatusChoices.PAID,
            paid_at=now,
        )
        self.message_user(request, f'تم تعليم {updated} كشف كمصروف.', level=messages.SUCCESS)

    @admin.action(description='↩ إعادة إلى مسودة')
    def action_reset_to_draft(self, request, queryset):
        updated = queryset.exclude(
            status=PayrollStatusChoices.PAID
        ).update(status=PayrollStatusChoices.DRAFT)
        self.message_user(request, f'تم إعادة {updated} كشف إلى المسودة.', level=messages.SUCCESS)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# ══════════════════════════════════════════════
#  تسجيل مخفي للـ Payroll الأصلي (لـ autocomplete)
# ══════════════════════════════════════════════

from apps.core.admin.payroll import PayrollAdmin as _PayrollOriginalAdmin


class _PayrollAutocompleteAdmin(_PayrollOriginalAdmin):
    """مخفي من الشريط الجانبي، يتيح autocomplete فقط."""
    def get_model_perms(self, request):
        return {}


# لا نُسجّل Payroll هنا - مسجّل في hr_system كـ PayrollProxy
# ══════════════════════════════════════════════
# إعدادات قسم المالية
# ══════════════════════════════════════════════

@admin.register(FinanceSettings)
class FinanceSettingsAdmin(admin.ModelAdmin):
    """
    إدارة إعدادات المالية العامة مثل نسبة التأمينات.
    """
    list_display = ('__str__', 'saudi_social_insurance_rate', 'non_saudi_social_insurance_rate')
    
    def has_add_permission(self, request):
        # Prevent adding multiple instances
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False
