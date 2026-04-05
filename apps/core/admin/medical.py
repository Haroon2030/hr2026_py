"""
إدارة التأمين الطبي والأعذار الطبية
=====================================
MedicalInsuranceAdmin, MedicalExcuseAdmin
"""

from rangefilter.filters import DateRangeFilter

from .base import BaseRequestAdmin, ApprovalStatusFilter, MedicalExcuseResource


class MedicalInsuranceAdmin(BaseRequestAdmin):
    """إدارة التأمينات الطبية للموظفين"""

    list_display = (
        'employee_name', 'branch', 'status_display',
        'branch_approval_display', 'dept_approval_display',
        'manager_approval_display',
    )
    list_filter = (
        'status', 'insurance_type', 'branch',
        ApprovalStatusFilter,
        ('created_at', DateRangeFilter),
    )
    search_fields = (
        'employee_name', 'insurance_type', 'details', 'branch'
    )

    fieldsets = (
        ('بيانات التأمين الطبي', {
            'fields': (
                'insurance_type', 'employee_name',
                'details', 'branch'
            )
        }),
        ('الملفات', {
            'fields': ('file_path',)
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


class MedicalExcuseAdmin(BaseRequestAdmin):
    """إدارة الأعذار الطبية - الإجازات المرضية"""
    resource_class = MedicalExcuseResource

    list_display = (
        'employee_name', 'branch',
        'status_display', 'branch_approval_display',
        'dept_approval_display', 'manager_approval_display',
    )
    list_filter = (
        'status', 'branch', 'department',
        ApprovalStatusFilter,
        ('created_at', DateRangeFilter),
    )
    search_fields = (
        'employee_name', 'employee_id_number', 'branch',
        'department', 'excuse_reason'
    )

    fieldsets = (
        ('بيانات الموظف', {
            'fields': (
                'employee_name', 'employee_id_number',
                'branch', 'department', 'cost_center'
            )
        }),
        ('تفاصيل العذر الطبي', {
            'fields': (
                'excuse_reason', 'excuse_date', 'excuse_duration',
                'file_path'
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
