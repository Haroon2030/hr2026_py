"""
إدارة ملفات الموظفين وإنهاء الخدمات
=====================================
EmployeeFileAdmin, TerminationFileAdmin
"""

from django.contrib import admin
from rangefilter.filters import DateRangeFilter

from django import forms
from apps.core.models import EmployeeFile, TerminationFile, DepartmentModel  # noqa: F401
from apps.core.pdf_export import export_employees_pdf
from .base import BaseRequestAdmin, EmployeeFileResource, ApprovalStatusFilter

class EmployeeFileForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'department' in self.fields:
            depts = [('', '---------')]
            if DepartmentModel.objects.exists():
                depts += [(d.name, d.name) for d in DepartmentModel.objects.all().order_by('name')]
            self.fields['department'] = forms.ChoiceField(
                choices=depts,
                required=False,
                label='القسم'
            )

    class Meta:
        model = EmployeeFile
        fields = '__all__'


class EmployeeFileAdmin(BaseRequestAdmin):
    """
    إدارة ملفات الموظفين - إضافة/تعديل/حذف/استعلام
    يدعم التصدير والاستيراد والاعتمادات الجماعية
    """
    form = EmployeeFileForm
    resource_class = EmployeeFileResource

    list_display = (
        'start_type_display', 'employee_name_display', 'start_date', 'branch',
        'branch_approval_display', 'dept_approval_display',
        'manager_approval_display', 'status_display'
    )
    list_display_links = ('employee_name_display',)
    list_filter = (
        'status', 'start_type', 'branch'
    )
    search_fields = (
        'employee_name', 'employee_number', 'national_id',
        'nationality', 'branch', 'department'
    )
    autocomplete_fields = ('assigned_to', 'completed_by')

    fieldsets = (
        ('بيانات الموظف', {
            'fields': (
                ('employee_name', 'employee_number'),
                ('national_id', 'nationality'),
                ('start_type', 'start_date')
            )
        }),
        ('الراتب والبدلات', {
            'fields': (
                ('salary',),
                ('transport_allowance', 'other_allowances'),
                ('overtime_allowance', 'insurance_percentage', 'external_allowance'),
            )
        }),
        ('الموقع التنظيمي', {
            'fields': (
                ('branch', 'department', 'cost_center'),
                ('organization', 'sponsorship', 'insurance_category'),
            )
        }),
        ('حالة العامل', {
            'fields': (
                ('is_suspended', 'suspended_from'),
                ('is_on_leave', 'leave_from'),
            )
        }),
        ('الملفات والمستندات', {
            'fields': (
                ('file_name', 'file_path'),
                'notes'
            )
        }),
        ('الحالة والتكليف', {
            'fields': (
                ('status', 'assigned_to'),
                ('department_filter', 'assigned_employee_number'),
                'assign_note',
            )
        }),
        ('سلسلة الاعتمادات الثلاثية', {
            'fields': (
                ('branch_manager_approval', 'branch_approved_by'),
                ('department_manager_approval', 'department_approved_by'),
                ('manager_approval', 'manager_approved_by'),
                'approval_notes'
            )
        }),
        ('معلومات النظام', {
            'fields': (
                ('uploaded_by', 'completed_by'),
                ('in_progress_at', 'completed_at'),
                ('created_at', 'updated_at')
            )
        }),
    )

    actions = [
        'approve_branch_manager', 'reject_branch_manager',
        'approve_department_manager', 'reject_department_manager',
        'approve_general_manager', 'reject_general_manager',
        'mark_in_progress', 'mark_completed', 'reset_approvals',
        export_employees_pdf,
    ]

    @admin.display(description='اسم الموظف')
    def employee_name_display(self, obj):
        from django.utils.html import format_html
        return format_html(
            '<div style="font-weight:900; color:#1a1d2e; font-size:13px; display:flex; align-items:center; gap:6px; white-space:nowrap;"> <i class="fas fa-user-circle" style="color:#5a6a85;"></i> {} </div>',
            obj.employee_name
        )

    @admin.display(description='نوع المباشرة')
    def start_type_display(self, obj):
        from django.utils.html import format_html
        if obj.start_type == 'new':
            return format_html('<span style="display:inline-flex; align-items:center; gap:4px; color:#047857; background:#e5fbe5; border:1px solid #a7f3d0; padding:4px 10px; border-radius:20px; font-size:11px; font-weight:800; white-space:nowrap;"><i class="fas fa-user-plus"></i> مباشرة جديدة</span>')
        else:
            return format_html('<span style="display:inline-flex; align-items:center; gap:4px; color:#b91c1c; background:#fee2e2; border:1px solid #fecaca; padding:4px 10px; border-radius:20px; font-size:11px; font-weight:800; white-space:nowrap;"><i class="fas fa-plane-arrival"></i> عودة من إجازة</span>')

    class Media:
        js = ('js/insurance_category_toggle.js',)


class TerminationFileAdmin(BaseRequestAdmin):
    """إدارة طلبات إنهاء الخدمات"""

    list_display = (
        'employee_name', 'branch', 'status_display',
        'branch_approval_display', 'dept_approval_display',
        'manager_approval_display', 'created_at'
    )
    list_filter = (
        'status', 'branch',
        ApprovalStatusFilter,
        ('created_at', DateRangeFilter),
    )
    search_fields = (
        'employee_name', 'employee_number', 'national_id',
        'nationality', 'branch'
    )

    fieldsets = (
        ('بيانات الموظف', {
            'fields': (
                'employee_name', 'employee_number',
                'national_id', 'nationality', 'branch'
            )
        }),
        ('تفاصيل الإنهاء', {
            'fields': ('last_working_date',)
        }),
        ('الملفات والملاحظات', {
            'fields': ('file_path', 'notes')
        }),
        ('الحالة والتكليف', {
            'fields': (
                'status', 'assigned_to', 'assign_note', 'department_filter'
            )
        }),
        ('سلسلة الاعتمادات الثلاثية', {
            'fields': (
                'branch_manager_approval', 'branch_approved_by',
                'department_manager_approval', 'department_approved_by',
                'manager_approval', 'manager_approved_by',
                'approval_notes'
            ),
            'classes': ('collapse',)
        }),
        ('معلومات النظام', {
            'fields': (
                'uploaded_by', 'completed_by', 'in_progress_at',
                'completed_at', 'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        }),
    )

    actions = [
        'approve_branch_manager', 'reject_branch_manager',
        'approve_department_manager', 'reject_department_manager',
        'approve_general_manager', 'reject_general_manager',
        'mark_in_progress', 'mark_completed', 'reset_approvals',
        'calculate_eosb_action'
    ]

    @admin.action(description='🧮 حاسبة مكافأة نهاية الخدمة (EOSB)')
    def calculate_eosb_action(self, request, queryset):
        from django.shortcuts import render
        from apps.core.models import EmployeeFile
        
        # We need to enrich the queryset with the employee's start_date and salary
        terminations_data = []
        for term in queryset:
            emp = EmployeeFile.objects.filter(employee_number=term.employee_number).first()
            if not emp:
                emp = EmployeeFile.objects.filter(national_id=term.national_id).first()
                
            terminations_data.append({
                'termination': term,
                'employee': emp,
                'start_date': emp.start_date.isoformat() if emp and emp.start_date else '',
                'salary': float(emp.salary) if emp and emp.salary else 0.0,
                'housing': float(emp.housing_allowance) if emp and emp.housing_allowance else 0.0,
            })

        return render(request, 'admin/hr/terminationfile/eosb_calculator.html', {
            'terminations_data': terminations_data,
            'title': 'حاسبة نهاية الخدمة (مُحسنة)'
        })
