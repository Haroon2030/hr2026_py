"""
إدارة سجلات الحضور / Attendance Admin
"""

from django.contrib import admin
from django.utils.html import format_html
from rangefilter.filters import DateRangeFilter
from import_export.admin import ImportExportModelAdmin

from apps.core.models import ApprovalStatus, RequestStatus
from apps.core.pdf_export import export_attendance_pdf
from .base import AttendanceRecordResource


class AttendanceRecordAdmin(ImportExportModelAdmin):
    """
    إدارة سجلات الحضور والانصراف.
    يدعم معالجة الدفعات والتصدير وسلسلة الاعتمادات الثلاثية.
    """
    resource_class = AttendanceRecordResource

    list_display = (
        'employee_name', 'branch', 'status_display',
    )
    list_filter = (
        'status', 'branch',
        ('attendance_date', DateRangeFilter),
    )
    search_fields = (
        'employee_name', 'title', 'branch',
        'batch_id', 'nationality', 'notes'
    )
    list_per_page = 25
    readonly_fields = ('created_at', 'updated_at')
    save_on_top = False
    autocomplete_fields = ('assigned_to',)

    fieldsets = (
        ('بيانات الحضور', {
            'fields': (
                'batch_id', 'batch_date', 'employee_name',
                'title', 'branch', 'nationality'
            )
        }),
        ('تفاصيل الدوام', {
            'fields': (
                'attendance_date', 'date_from',
                'shift_start', 'shift_end', 'notes'
            )
        }),
        ('الحالة والاعتمادات', {
            'fields': (
                'status', 'assigned_to',
                'branch_manager_approval',
                'department_manager_approval',
                'manager_approval', 'approval_notes'
            )
        }),
        ('معلومات النظام', {
            'fields': ('uploaded_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description='الحالة')
    def status_display(self, obj):
        colors = {
            'pending':     '#ffc107',
            'in_progress': '#17a2b8',
            'completed':   '#28a745',
            'approved':    '#28a745',
            'rejected':    '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background:{}; color:#fff; padding:2px 8px; '
            'border-radius:10px; font-size:11px;">{}</span>',
            color, obj.get_status_display()
        )

    actions = ['approve_batch', 'reject_batch', 'mark_complete', export_attendance_pdf]

    @admin.action(description='✅ اعتماد سجلات الحضور المحددة')
    def approve_batch(self, request, queryset):
        updated = queryset.update(
            status=RequestStatus.APPROVED,
            manager_approval=ApprovalStatus.APPROVED
        )
        self.message_user(request, f'تم اعتماد {updated} سجل حضور')

    @admin.action(description='❌ رفض سجلات الحضور المحددة')
    def reject_batch(self, request, queryset):
        updated = queryset.update(
            status=RequestStatus.REJECTED,
            manager_approval=ApprovalStatus.REJECTED
        )
        self.message_user(request, f'تم رفض {updated} سجل حضور')

    @admin.action(description='✔ تحديد كمكتمل')
    def mark_complete(self, request, queryset):
        updated = queryset.update(status=RequestStatus.COMPLETED)
        self.message_user(request, f'تم إكمال {updated} سجل حضور')

    def save_model(self, request, obj, form, change):
        if not change:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)
