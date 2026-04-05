"""
إدارة رسائل النظام، الإشعارات، وسجل النشاطات
================================================
SystemMessageAdmin, NotificationAdmin, ActivityLogAdmin
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from rangefilter.filters import DateRangeFilter

# نماذج هذه الصفحة مُسجّلة في apps/system/admin.py كـ proxy
# الاستيرادات أدناه للتوثيق فقط
from apps.core.models import (  # noqa: F401
    SystemMessage, Notification, ActivityLog,
    WorkerStatusLog, UserMessage, MessageStatus,
)


class SystemMessageAdmin(admin.ModelAdmin):
    """إدارة رسائل النظام والبث لجميع المستخدمين"""

    list_display = (
        'title', 'message_type_display', 'is_active',
        'created_by', 'created_at'
    )
    list_filter = ('message_type', 'is_active')
    search_fields = ('title', 'content')
    list_editable = ('is_active',)
    list_per_page = 20
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('محتوى الرسالة', {
            'fields': ('title', 'content', 'message_type', 'is_active')
        }),
        ('معلومات النظام', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description='النوع')
    def message_type_display(self, obj):
        colors = {
            'info':    '#17a2b8',
            'warning': '#ffc107',
            'success': '#28a745',
            'danger':  '#dc3545',
        }
        color = colors.get(obj.message_type, '#6c757d')
        return format_html(
            '<span style="color:{}; font-weight:bold;">{}</span>',
            color, obj.get_message_type_display()
        )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class NotificationAdmin(admin.ModelAdmin):
    """إدارة إشعارات المستخدمين"""

    list_display = (
        'title', 'user', 'notification_type',
        'is_read', 'read_at', 'created_at'
    )
    list_filter = (
        'notification_type', 'is_read',
        ('created_at', DateRangeFilter),
    )
    search_fields = ('title', 'message', 'user__username', 'user__first_name')
    list_editable = ('is_read',)
    list_per_page = 30
    readonly_fields = ('created_at', 'read_at')
    autocomplete_fields = ('user',)

    fieldsets = (
        ('الإشعار', {
            'fields': (
                'user', 'title', 'message',
                'notification_type', 'link', 'icon'
            )
        }),
        ('الحالة', {
            'fields': ('is_read', 'read_at', 'created_at')
        }),
    )

    actions = ['mark_as_read', 'mark_as_unread']

    @admin.action(description='✓ تعليم كمقروء')
    def mark_as_read(self, request, queryset):
        updated = queryset.update(is_read=True, read_at=timezone.now())
        self.message_user(request, f'تم تعليم {updated} إشعار كمقروء')

    @admin.action(description='● تعليم كغير مقروء')
    def mark_as_unread(self, request, queryset):
        updated = queryset.update(is_read=False, read_at=None)
        self.message_user(request, f'تم تعليم {updated} إشعار كغير مقروء')


class ActivityLogAdmin(admin.ModelAdmin):
    """
    عرض سجل النشاطات - للقراءة فقط (لا يمكن إضافة أو تعديل يدوياً)
    """

    list_display = (
        'username', 'action_display', 'module',
        'description_short', 'target_id',
        'ip_address', 'created_at'
    )
    list_filter = (
        'action', 'module',
        ('created_at', DateRangeFilter),
    )
    search_fields = (
        'username', 'description', 'module',
        'ip_address', 'request_url'
    )
    list_per_page = 30
    readonly_fields = (
        'user', 'username', 'action', 'module', 'description',
        'target_id', 'old_data', 'new_data', 'ip_address',
        'user_agent', 'request_url', 'request_method', 'created_at'
    )

    fieldsets = (
        ('تفاصيل النشاط', {
            'fields': (
                'user', 'username', 'action', 'module',
                'description', 'target_id'
            )
        }),
        ('البيانات قبل/بعد التعديل', {
            'fields': ('old_data', 'new_data'),
            'classes': ('collapse',)
        }),
        ('معلومات الطلب', {
            'fields': (
                'ip_address', 'user_agent',
                'request_url', 'request_method', 'created_at'
            ),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description='العملية')
    def action_display(self, obj):
        colors = {
            'create':   '#28a745',
            'update':   '#ffc107',
            'delete':   '#dc3545',
            'view':     '#17a2b8',
            'login':    '#007bff',
            'logout':   '#6c757d',
            'approve':  '#28a745',
            'reject':   '#dc3545',
            'upload':   '#6f42c1',
        }
        color = colors.get(obj.action, '#6c757d')
        return format_html(
            '<span style="color:{}; font-weight:bold;">{}</span>',
            color, obj.get_action_display()
        )

    @admin.display(description='الوصف')
    def description_short(self, obj):
        if obj.description and len(obj.description) > 80:
            return obj.description[:80] + '...'
        return obj.description or '-'

    def has_add_permission(self, request):
        """منع إضافة سجلات يدوياً"""
        return False

    def has_change_permission(self, request, obj=None):
        """منع تعديل السجلات"""
        return False

    def has_delete_permission(self, request, obj=None):
        """السماح بالحذف للمدير العام فقط"""
        return request.user.is_superuser


class WorkerStatusLogAdmin(admin.ModelAdmin):
    """إدارة سجل حالات العمال (إيقاف/إجازة)"""

    list_display = (
        'employee_display', 'status_type_display', 'start_date',
        'end_date', 'is_active_display', 'days_count', 'created_at'
    )
    list_filter = ('status_type', 'is_active', ('start_date', DateRangeFilter))
    search_fields = ('employee__employee_name', 'employee__employee_number', 'reason')
    raw_id_fields = ('employee',)
    list_per_page = 30
    readonly_fields = ('created_at', 'created_by')
    
    fieldsets = (
        ('بيانات الموظف', {
            'fields': ('employee',)
        }),
        ('تفاصيل الحالة', {
            'fields': (
                'status_type',
                ('start_date', 'end_date'),
                'is_active',
                'reason'
            )
        }),
        ('معلومات النظام', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description='الموظف')
    def employee_display(self, obj):
        return format_html(
            '<div style="font-weight:bold;">{}</div>'
            '<small style="color:#666;">{}</small>',
            obj.employee.employee_name,
            obj.employee.employee_number or '-'
        )

    @admin.display(description='نوع الحالة')
    def status_type_display(self, obj):
        if obj.status_type == 'suspended':
            return format_html(
                '<span style="display:inline-flex; align-items:center; gap:4px; color:#b91c1c; background:#fee2e2; border:1px solid #fecaca; padding:4px 10px; border-radius:20px; font-size:11px; font-weight:800;"><i class="fas fa-ban"></i> موقوف</span>'
            )
        else:
            return format_html(
                '<span style="display:inline-flex; align-items:center; gap:4px; color:#0369a1; background:#e0f2fe; border:1px solid #7dd3fc; padding:4px 10px; border-radius:20px; font-size:11px; font-weight:800;"><i class="fas fa-plane"></i> إجازة</span>'
            )

    @admin.display(description='الحالة')
    def is_active_display(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="color:#047857; font-weight:bold;"><i class="fas fa-clock"></i> جاري</span>'
            )
        else:
            return format_html(
                '<span style="color:#6b7280;"><i class="fas fa-check-circle"></i> منتهي</span>'
            )

    @admin.display(description='عدد الأيام')
    def days_count(self, obj):
        from datetime import date
        end = obj.end_date if obj.end_date else date.today()
        days = (end - obj.start_date).days + 1
        return format_html(
            '<span style="font-weight:bold; color:#4f46e5;">{} يوم</span>',
            days
        )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    actions = ['end_status']

    @admin.action(description='إنهاء الحالة (رفع الإيقاف/الإجازة)')
    def end_status(self, request, queryset):
        from datetime import date
        updated = queryset.filter(is_active=True).update(
            is_active=False,
            end_date=date.today()
        )
        self.message_user(request, f'تم إنهاء {updated} حالة بنجاح.')
