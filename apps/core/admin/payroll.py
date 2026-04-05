"""
إدارة الأقسام، كشوف الرواتب، وتقييمات الأداء
================================================
DepartmentModelAdmin, PayrollAdmin, PerformanceReviewAdmin
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from import_export import resources, fields
from import_export.admin import ImportExportModelAdmin
from rangefilter.filters import DateRangeFilter

from apps.core.models import (
    DepartmentModel, Payroll, PerformanceReview,
    PayrollStatusChoices,
)
from apps.core.pdf_export import export_payroll_pdf, export_performance_pdf


# ==============================
# موارد التصدير
# ==============================

class PayrollResource(resources.ModelResource):
    """مورد تصدير/استيراد كشوف الرواتب"""
    employee_name = fields.Field(
        attribute='employee__employee_name', column_name='اسم الموظف'
    )
    department_name = fields.Field(
        attribute='department__name', column_name='القسم'
    )

    class Meta:
        model = Payroll
        fields = (
            'id', 'employee_name', 'department_name',
            'period_month', 'period_year', 'basic_salary',
            'housing_allowance', 'transport_allowance', 'other_allowances',
            'overtime_hours', 'overtime_amount', 'deductions',
            'social_insurance', 'absence_deduction', 'advance_deduction',
            'net_salary', 'status'
        )
        export_order = fields


class PerformanceReviewResource(resources.ModelResource):
    """مورد تصدير/استيراد تقييمات الأداء"""
    employee_name = fields.Field(
        attribute='employee__employee_name', column_name='اسم الموظف'
    )
    reviewer_name = fields.Field(
        attribute='reviewer__username', column_name='المُقيّم'
    )

    class Meta:
        model = PerformanceReview
        fields = (
            'id', 'employee_name', 'reviewer_name',
            'review_period_start', 'review_period_end',
            'work_quality', 'productivity', 'teamwork',
            'punctuality', 'initiative', 'communication',
            'score', 'overall_rating'
        )
        export_order = fields


# ==============================
# Inline للرواتب داخل الأقسام
# ==============================

class PayrollInline(admin.TabularInline):
    """عرض كشوف الرواتب المرتبطة بالقسم"""
    model = Payroll
    extra = 0
    fields = ('employee', 'period_month', 'period_year', 'basic_salary', 'net_salary', 'status')
    readonly_fields = ('net_salary',)
    show_change_link = True


# ==============================
# إدارة الأقسام
# ==============================

class DepartmentModelAdmin(admin.ModelAdmin):
    """إدارة الأقسام والإدارات - الهيكل التنظيمي"""
    list_display = (
        'name', 'code', 'manager', 'parent',
        'employee_count_display', 'is_active', 'created_at'
    )
    list_filter = ('is_active', 'parent')
    search_fields = ('name', 'code', 'description')
    list_editable = ('is_active',)
    list_per_page = 25
    autocomplete_fields = ('manager', 'parent')

    fieldsets = (
        ('بيانات القسم / الإدارة', {
            'fields': ('name', 'code', 'manager', 'parent', 'description', 'is_active')
        }),
        ('معلومات النظام', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('created_at',)

    @admin.display(description='عدد الموظفين')
    def employee_count_display(self, obj):
        count = obj.payroll_employees.exclude(status='cancelled').count()
        return format_html(
            '<span style="background:#17a2b8; color:#fff; padding:2px 10px; '
            'border-radius:10px; font-size:11px;">{}</span>', count
        )


class _DepartmentAutocompleteAdmin(DepartmentModelAdmin):
    """تسجيل مخفي يتيح autocomplete دون ظهور القسم في الشريط الجانبي."""
    def get_model_perms(self, request):
        return {}


admin.site.register(DepartmentModel, _DepartmentAutocompleteAdmin)


# ==============================
# إدارة كشوف الرواتب
# ==============================

class PayrollAdmin(ImportExportModelAdmin):
    """إدارة كشوف الرواتب الشهرية"""
    resource_class = PayrollResource

    list_display = (
        'employee', 'department', 'period_display',
        'basic_salary', 'total_earnings_display', 'total_deductions_display',
        'net_salary_display', 'status_display', 'created_at'
    )
    list_filter = (
        'status', 'period_year', 'period_month', 'department',
        ('created_at', DateRangeFilter),
    )
    search_fields = (
        'employee__employee_name', 'employee__employee_number',
        'department__name', 'notes'
    )
    list_per_page = 25
    autocomplete_fields = ('department', 'approved_by', 'created_by')
    raw_id_fields = ('employee',)
    readonly_fields = ('net_salary', 'created_at', 'updated_at', 'approved_at', 'paid_at')

    fieldsets = (
        ('بيانات الموظف والفترة', {
            'fields': (
                'employee', 'department', 'period_month', 'period_year'
            )
        }),
        ('الراتب الأساسي والبدلات', {
            'fields': (
                'basic_salary', 'housing_allowance',
                'transport_allowance', 'other_allowances',
                'overtime_hours', 'overtime_amount'
            )
        }),
        ('الخصومات', {
            'fields': (
                'deductions', 'social_insurance',
                'absence_deduction', 'advance_deduction'
            )
        }),
        ('الصافي والحالة', {
            'fields': (
                'net_salary', 'status', 'notes'
            )
        }),
        ('الاعتماد والصرف', {
            'fields': (
                'approved_by', 'approved_at',
                'paid_at', 'created_by'
            ),
            'classes': ('collapse',)
        }),
        ('معلومات النظام', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['approve_payroll', 'mark_paid', 'mark_cancelled', 'recalculate_salary', export_payroll_pdf, 'print_detailed_payslips', 'export_wps_csv']

    @admin.display(description='الفترة')
    def period_display(self, obj):
        months = {
            1: 'يناير', 2: 'فبراير', 3: 'مارس', 4: 'أبريل',
            5: 'مايو', 6: 'يونيو', 7: 'يوليو', 8: 'أغسطس',
            9: 'سبتمبر', 10: 'أكتوبر', 11: 'نوفمبر', 12: 'ديسمبر'
        }
        return f"{months.get(obj.period_month, obj.period_month)} {obj.period_year}"

    @admin.display(description='إجمالي المستحقات')
    def total_earnings_display(self, obj):
        return format_html(
            '<span style="color:#28a745; font-weight:bold;">{:,.2f}</span>',
            obj.total_earnings
        )

    @admin.display(description='إجمالي الخصومات')
    def total_deductions_display(self, obj):
        return format_html(
            '<span style="color:#dc3545; font-weight:bold;">{:,.2f}</span>',
            obj.total_deductions
        )

    @admin.display(description='صافي الراتب')
    def net_salary_display(self, obj):
        return format_html(
            '<span style="background:#1a1d2e; color:#fff; padding:2px 10px; '
            'border-radius:10px; font-weight:bold;">{:,.2f}</span>',
            obj.net_salary
        )

    @admin.display(description='الحالة')
    def status_display(self, obj):
        colors = {
            'draft':     '#6c757d',
            'pending':   '#ffc107',
            'approved':  '#28a745',
            'paid':      '#007bff',
            'cancelled': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background:{}; color:#fff; padding:2px 8px; '
            'border-radius:10px; font-size:11px;">{}</span>',
            color, obj.get_status_display()
        )

    @admin.action(description='✅ اعتماد كشوف الرواتب')
    def approve_payroll(self, request, queryset):
        updated = queryset.filter(
            status__in=[PayrollStatusChoices.DRAFT, PayrollStatusChoices.PENDING]
        ).update(
            status=PayrollStatusChoices.APPROVED,
            approved_by=request.user,
            approved_at=timezone.now()
        )
        self.message_user(request, f'تم اعتماد {updated} كشف رواتب')

    @admin.action(description='💰 تأكيد صرف الرواتب')
    def mark_paid(self, request, queryset):
        updated = queryset.filter(
            status=PayrollStatusChoices.APPROVED
        ).update(
            status=PayrollStatusChoices.PAID,
            paid_at=timezone.now()
        )
        self.message_user(request, f'تم تأكيد صرف {updated} كشف رواتب')

    @admin.action(description='❌ إلغاء كشوف الرواتب')
    def mark_cancelled(self, request, queryset):
        updated = queryset.exclude(
            status=PayrollStatusChoices.PAID
        ).update(status=PayrollStatusChoices.CANCELLED)
        self.message_user(request, f'تم إلغاء {updated} كشف رواتب')

    @admin.action(description='🔄 إعادة حساب صافي الراتب')
    def recalculate_salary(self, request, queryset):
        count = 0
        for payroll in queryset:
            payroll.calculate_net_salary()
            payroll.save(update_fields=['net_salary'])
            count += 1
        self.message_user(request, f'تم إعادة حساب {count} كشف رواتب')

    @admin.action(description='🖨️ طباعة مسيرات الرواتب المفصلة (Payslips)')
    def print_detailed_payslips(self, request, queryset):
        from django.shortcuts import render
        context = {
            'payrolls': queryset,
            'title': 'طباعة مسير الرواتب - Payslip',
        }
        return render(request, 'admin/hr/payroll/payslip_print.html', context)

    @admin.action(description='🏦 تصدير الرواتب للبنك / حماية الأجور (CSV)')
    def export_wps_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response.write(b'\xef\xbb\xbf')  # BOM لضمان دعم Excel للغة العربية بشكل صحيح
        response['Content-Disposition'] = 'attachment; filename="wps_salary_transfer.csv"'
        
        writer = csv.writer(response)
        # ترويسة الأعمدة لمعايير البنوك السعودية
        writer.writerow([
            'رقم الموظف', 
            'رقم الهوية/الإقامة', 
            'اسم الموظف', 
            'الراتب الأساسي', 
            'بدل السكن', 
            'بدلات أخرى', 
            'إجمالي الخصومات', 
            'صافي الراتب المحول'
        ])
        
        for p in queryset:
            emp = p.employee
            writer.writerow([
                getattr(emp, 'employee_number', '') or '',
                getattr(emp, 'national_id', '') or '',
                getattr(emp, 'employee_name', '') or '',
                p.basic_salary,
                p.housing_allowance,
                p.transport_allowance + p.other_allowances,
                p.total_deductions,
                p.net_salary
            ])
            
        self.message_user(request, 'تم تصدير ملف البنك بنجاح.')
        return response

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# ==============================
# إدارة تقييمات الأداء
# ==============================

from django import forms

class PerformanceReviewForm(forms.ModelForm):
    class Meta:
        model = PerformanceReview
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        rating_fields = ['work_quality', 'productivity', 'teamwork', 'punctuality', 'initiative', 'communication']
        for field in rating_fields:
            if field in self.fields:
                self.fields[field].widget = forms.NumberInput(attrs={
                    'min': '1', 
                    'max': '5', 
                    'inputmode': 'numeric',
                    'title': 'يجب أن يكون الرقم بين 1 و 5 فقط'
                })

class PerformanceReviewAdmin(ImportExportModelAdmin):
    """إدارة تقييمات أداء الموظفين الدورية"""
    resource_class = PerformanceReviewResource
    form = PerformanceReviewForm

    list_display = (
        'employee', 'reviewer', 'period_display',
        'score_display', 'rating_display',
        'is_acknowledged', 'created_at'
    )
    list_filter = (
        'overall_rating', 'is_acknowledged',
        ('review_period_end', DateRangeFilter),
        ('created_at', DateRangeFilter),
    )
    search_fields = (
        'employee__employee_name', 'employee__employee_number',
        'reviewer__username', 'strengths', 'weaknesses', 'goals'
    )
    list_per_page = 25
    autocomplete_fields = ('reviewer',)
    raw_id_fields = ('employee',)
    readonly_fields = ('score', 'overall_rating', 'created_at', 'updated_at', 'acknowledged_at')

    fieldsets = (
        ('بيانات التقييم', {
            'fields': (
                ('employee', 'reviewer'),
                ('review_period_start', 'review_period_end')
            )
        }),
        ('معايير التقييم (1-5)', {
            'fields': (
                ('work_quality', 'productivity'),
                ('teamwork', 'punctuality'),
                ('initiative', 'communication'),
            ),
            'description': 'يتم التقييم بالأرقام من 1 إلى 5 فقط: 1 = ضعيف، 2 = مقبول، 3 = جيد، 4 = جيد جداً، 5 = ممتاز'
        }),
        ('النتيجة الإجمالية', {
            'fields': (('score', 'overall_rating'),),
        }),
        ('الملاحظات والأهداف التطويرية', {
            'fields': (
                'strengths', 'weaknesses', 'goals',
                'reviewer_comments', 'employee_comments'
            )
        }),
        ('اطلاع الموظف', {
            'fields': (('is_acknowledged', 'acknowledged_at'),),
        }),
        ('معلومات النظام', {
            'fields': (('created_at', 'updated_at'),),
            'classes': ('collapse',)
        }),
    )

    actions = ['mark_acknowledged', export_performance_pdf]

    @admin.display(description='فترة التقييم')
    def period_display(self, obj):
        return f"{obj.review_period_start} → {obj.review_period_end}"

    @admin.display(description='الدرجة')
    def score_display(self, obj):
        color = '#28a745' if obj.score >= 3.5 else '#ffc107' if obj.score >= 2.5 else '#dc3545'
        return format_html(
            '<span style="color:{}; font-weight:bold; font-size:14px;">{}/5</span>',
            color, round(obj.score, 1)
        )

    @admin.display(description='التقييم')
    def rating_display(self, obj):
        colors = {
            'excellent': '#28a745',
            'very_good': '#17a2b8',
            'good':      '#ffc107',
            'acceptable':'#fd7e14',
            'poor':      '#dc3545',
        }
        color = colors.get(obj.overall_rating, '#6c757d')
        return format_html(
            '<span style="color:{}; font-weight:bold;">{}</span>',
            color, obj.get_overall_rating_display()
        )

    @admin.action(description='✓ تأكيد اطلاع الموظفين')
    def mark_acknowledged(self, request, queryset):
        from django.utils import timezone as tz
        updated = queryset.filter(is_acknowledged=False).update(
            is_acknowledged=True,
            acknowledged_at=tz.now()
        )
        self.message_user(request, f'تم تأكيد اطلاع {updated} موظف')
