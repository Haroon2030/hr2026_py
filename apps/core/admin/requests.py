"""
إدارة الطلبات: السلف، الإجازات، المخالفات، تعديل الرواتب، طلبات النقل
=========================================================================
"""

from django.contrib import admin
from rangefilter.filters import DateRangeFilter

from apps.core.pdf_export import export_leaves_pdf
from .base import (
    BaseRequestAdmin, ApprovalStatusFilter,
    AdvanceFileResource, StatementFileResource,
    ViolationFileResource, SalaryAdjustmentResource,
    TransferRequestResource,
)


class AdvanceFileAdmin(BaseRequestAdmin):
    """إدارة طلبات السلف المالية (سلف الرواتب)"""
    resource_class = AdvanceFileResource

    list_display = (
        'employee_name', 'branch', 'status_display',
        'branch_approval_display', 'dept_approval_display',
        'manager_approval_display',
    )
    list_filter = (
        'status', 'branch',
        ApprovalStatusFilter,
        ('created_at', DateRangeFilter),
    )
    search_fields = (
        'employee_name', 'employee_number', 'branch', 'notes'
    )

    fieldsets = (
        ('بيانات سلفة الراتب', {
            'fields': (
                'employee_name', 'employee_number',
                'advance_amount', 'installments', 'advance_date', 'branch'
            )
        }),
        ('الملفات والملاحظات', {
            'fields': ('file_path', 'file_name', 'notes')
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
    ]


class StatementFileAdmin(BaseRequestAdmin):
    """إدارة الإفادات وطلبات الإجازات السنوية والطارئة"""
    resource_class = StatementFileResource

    list_display = (
        'employee_name_display', 'branch', 'status_display',
        'branch_approval_display', 'dept_approval_display',
        'manager_approval_display',
    )
    list_display_links = ('employee_name_display',)
    list_filter = (
        'status', 'statement_type', 'branch'
    )
    search_fields = (
        'employee_name', 'employee_number', 'branch', 'notes'
    )

    @admin.display(description='اسم الموظف')
    def employee_name_display(self, obj):
        from django.utils.html import format_html
        return format_html(
            '<div style="font-weight:900; color:#1a1d2e; font-size:13px; display:flex; align-items:center; gap:6px; white-space:nowrap;"> <i class="fas fa-user-circle" style="color:#5a6a85;"></i> {} </div>',
            obj.employee_name
        )

    @admin.display(description='النوع')
    def statement_type_display(self, obj):
        from django.utils.html import format_html
        val = obj.statement_type
        # simple colors based on type
        if val == 'annual':
            color, bg, border, icon = '#047857', '#e5fbe5', '#a7f3d0', 'fa-calendar-check'
        elif val == 'emergency':
            color, bg, border, icon = '#b91c1c', '#fee2e2', '#fecaca', 'fa-exclamation-circle'
        else:
            color, bg, border, icon = '#1d4ed8', '#dbeafe', '#bfdbfe', 'fa-file-alt'
            
        type_labels = {
            'annual': 'سنوية',
            'emergency': 'طارئة',
            'sick': 'مرضية',
            'unpaid': 'بدون راتب',
            'vacation': 'إجازة'
        }
        label = type_labels.get(val, val) if val else 'غير محدد'
        
        return format_html('<span style="display:inline-flex; align-items:center; gap:4px; color:{}; background:{}; border:1px solid {}; padding:4px 10px; border-radius:20px; font-size:11px; font-weight:800; white-space:nowrap;"><i class="fas {}"></i> {}</span>', color, bg, border, icon, label)

    fieldsets = (
        ('بيانات الإجازة', {
            'fields': (
                ('employee_name', 'employee_number'),
                ('statement_type', 'branch')
            )
        }),
        ('تفاصيل الإجازة', {
            'fields': (
                ('vacation_days', 'vacation_start', 'vacation_end'),
                'vacation_balance'
            ),
            'description': 'تعبأ عند طلب إجازة - رصيد الإجازات وفق نظام العمل السعودي (30 يوم/سنة)'
        }),
        ('الملفات والملاحظات', {
            'fields': (
                ('file_name', 'file_path'),
                'notes'
            )
        }),
        ('الحالة والتكليف', {
            'fields': (
                ('status', 'assigned_to'), 
                ('department_filter', 'assign_note')
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
        export_leaves_pdf,
    ]


class ViolationFileAdmin(BaseRequestAdmin):
    """إدارة المخالفات والإجراءات التأديبية"""
    resource_class = ViolationFileResource

    list_display = (
        'employee_name', 'branch', 'status_display',
        'branch_approval_display', 'dept_approval_display',
        'manager_approval_display',
    )
    list_filter = (
        'status', 'violation_type', 'branch',
        ApprovalStatusFilter,
        ('created_at', DateRangeFilter),
    )
    search_fields = (
        'employee_name', 'employee_number', 'violation_type',
        'branch', 'violation_notes'
    )

    fieldsets = (
        ('بيانات الإجراء التأديبي', {
            'fields': (
                'violation_type', 'employee_name', 'employee_number',
                'violation_date', 'branch',
                'employee_branch', 'employee_department'
            )
        }),
        ('تفاصيل إضافية', {
            'fields': (
                'file_path', 'violation_notes', 'employee_statement'
            )
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
    ]


class SalaryAdjustmentAdmin(BaseRequestAdmin):
    """إدارة تعديلات الرواتب والزيادات الدورية"""
    resource_class = SalaryAdjustmentResource

    list_display = (
        'employee_name_display', 'branch', 'status_display',
        'branch_approval_display', 'dept_approval_display',
        'manager_approval_display',
    )

    @admin.display(description='اسم الموظف', ordering='employee_name')
    def employee_name_display(self, obj):
        from django.utils.html import format_html
        return format_html(
            '<div style="font-weight:900; color:#1a1d2e; font-size:13px; display:inline-flex; align-items:center; gap:6px; white-space:nowrap;"> <i class="fas fa-user-circle" style="color:#5a6a85;"></i> {} </div>',
            obj.employee_name
        )
        
    list_filter = (
        'status', 'branch',
        ApprovalStatusFilter,
        ('created_at', DateRangeFilter),
    )
    search_fields = (
        'employee_name', 'employee_number', 'branch',
        'department', 'adjustment_reason'
    )

    fieldsets = (
        ('بيانات الموظف', {
            'fields': (
                'employee_ref', 'employee_name', 'employee_number',
                'branch', 'department', 'cost_center'
            )
        }),
        ('تفاصيل تعديل الراتب', {
            'fields': (
                'current_salary', 'salary_increase', 'new_salary',
                'installments', 'adjustment_reason', 'notes'
            ),
            'description': 'الراتب الجديد = الراتب الحالي + الزيادة (يُحسب تلقائياً)'
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
    ]


class EmployeeTransferRequestAdmin(BaseRequestAdmin):
    """إدارة طلبات نقل الموظفين بين الفروع والأقسام"""
    resource_class = TransferRequestResource

    list_display = (
        'employee_name', 'current_branch', 'status_display',
        'branch_approval_display', 'dept_approval_display',
        'manager_approval_display',
    )
    list_filter = (
        'status', 'current_branch',
        ApprovalStatusFilter,
        ('created_at', DateRangeFilter),
    )
    search_fields = (
        'employee_name', 'employee_id_number',
        'current_branch', 'requested_branch',
        'transfer_reason'
    )

    fieldsets = (
        ('بيانات الموظف', {
            'fields': ('employee_name', 'employee_id_number')
        }),
        ('تفاصيل طلب النقل', {
            'fields': (
                ('current_branch', 'requested_branch'),
                ('current_department', 'requested_department'),
                ('current_cost_center', 'new_cost_center'),
                'transfer_reason', 'preferred_date'
            )
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
    ]
