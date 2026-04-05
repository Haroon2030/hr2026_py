"""
تسجيل نماذج إدارة النظام - تظهر تحت قسم "إدارة النظام" في الشريط الجانبي.
تستخدم كلاسات Admin الأصلية من hr.admin مع نماذج Proxy.
"""
from django.contrib import admin
from django.db import models
from django.utils import timezone

from apps.core.admin.users import UserAdmin as OriginalUserAdmin
from apps.core.admin.payroll import DepartmentModelAdmin, PerformanceReviewAdmin
from apps.core.admin.system import SystemMessageAdmin, NotificationAdmin, ActivityLogAdmin

from .models import (
    UserProxy,
    DepartmentModelProxy,
    PerformanceReviewProxy,
    SystemMessageProxy,
    NotificationProxy,
    ActivityLogProxy,
    BranchProxy,
    CostCenterProxy,
    OrganizationProxy,
    SponsorshipProxy,
    UserMessageProxy,
)


@admin.register(UserProxy)
class UserProxyAdmin(OriginalUserAdmin):
    pass


@admin.register(DepartmentModelProxy)
class DepartmentModelProxyAdmin(DepartmentModelAdmin):
    pass


@admin.register(PerformanceReviewProxy)
class PerformanceReviewProxyAdmin(PerformanceReviewAdmin):
    pass


@admin.register(SystemMessageProxy)
class SystemMessageProxyAdmin(SystemMessageAdmin):
    pass


@admin.register(NotificationProxy)
class NotificationProxyAdmin(NotificationAdmin):
    pass


@admin.register(ActivityLogProxy)
class ActivityLogProxyAdmin(ActivityLogAdmin):
    pass


@admin.register(BranchProxy)
class BranchProxyAdmin(admin.ModelAdmin):
    """إدارة الفروع"""
    list_display = ('id', 'name_display', 'employees_count', 'requests_count', 'created_at_display')
    search_fields = ('name',)
    ordering = ('name',)
    list_per_page = 25

    @admin.display(description='#')
    def id_display(self, obj):
        return obj.id

    @admin.display(description='اسم الفرع', ordering='name')
    def name_display(self, obj):
        from django.utils.html import format_html
        return format_html(
            '<div style="display:inline-flex; align-items:center; gap:10px; padding:8px 18px; '
            'background:linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); '
            'border:1px solid #93c5fd; border-radius:12px; font-weight:700; color:#1e40af; '
            'font-size:14px; min-width:200px; box-shadow:0 2px 4px rgba(59,130,246,0.1);'
            'transition: all 0.2s ease;">'
            '<span style="display:flex;align-items:center;justify-content:center;width:32px;height:32px;'
            'background:linear-gradient(135deg,#3b82f6,#2563eb);border-radius:8px;">'
            '<i class="fas fa-building" style="color:#fff;font-size:14px;"></i></span>'
            '<span>{}</span></div>',
            obj.name
        )

    @admin.display(description='عدد الموظفين')
    def employees_count(self, obj):
        from django.utils.html import format_html
        from apps.core.models import EmployeeFile
        count = EmployeeFile.objects.filter(branch=obj).count()
        if count > 0:
            color = '#059669' if count >= 10 else '#d97706' if count >= 5 else '#6b7280'
            bg = '#ecfdf5' if count >= 10 else '#fffbeb' if count >= 5 else '#f9fafb'
            return format_html(
                '<span style="display:inline-flex;align-items:center;justify-content:center;'
                'padding:6px 14px;background:{};border-radius:20px;font-weight:700;'
                'color:{};font-size:13px;min-width:50px;">'
                '<i class="fas fa-users" style="margin-left:6px;"></i>{}</span>',
                bg, color, count
            )
        return format_html(
            '<span style="color:#9ca3af;font-size:12px;">لا يوجد</span>'
        )

    @admin.display(description='الطلبات النشطة')
    def requests_count(self, obj):
        from django.utils.html import format_html
        from apps.core.models import EmployeeFile
        count = EmployeeFile.objects.filter(branch=obj, status='pending').count()
        if count > 0:
            return format_html(
                '<span style="display:inline-flex;align-items:center;justify-content:center;'
                'padding:6px 14px;background:#fef3c7;border-radius:20px;font-weight:700;'
                'color:#b45309;font-size:13px;min-width:50px;animation:pulse 2s infinite;">'
                '<i class="fas fa-clock" style="margin-left:6px;"></i>{}</span>',
                count
            )
        return format_html(
            '<span style="display:inline-flex;align-items:center;justify-content:center;'
            'padding:6px 14px;background:#f0fdf4;border-radius:20px;font-weight:600;'
            'color:#16a34a;font-size:12px;">'
            '<i class="fas fa-check" style="margin-left:4px;"></i>لا يوجد</span>'
        )

    @admin.display(description='تاريخ الإنشاء', ordering='created_at')
    def created_at_display(self, obj):
        from django.utils.html import format_html
        if obj.created_at:
            return format_html(
                '<span style="color:#64748b;font-size:12px;">'
                '<i class="fas fa-calendar-alt" style="margin-left:4px;"></i>{}</span>',
                obj.created_at.strftime('%Y-%m-%d')
            )
        return '-'


@admin.register(CostCenterProxy)
class CostCenterProxyAdmin(admin.ModelAdmin):
    """إدارة مراكز التكلفة"""
    list_display = ('id', 'name_display', 'employees_count', 'created_at_display')
    search_fields = ('name',)
    ordering = ('name',)
    list_per_page = 25

    @admin.display(description='مركز التكلفة', ordering='name')
    def name_display(self, obj):
        from django.utils.html import format_html
        return format_html(
            '<div style="display:inline-flex; align-items:center; gap:10px; padding:8px 18px; '
            'background:linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); '
            'border:1px solid #86efac; border-radius:12px; font-weight:700; color:#166534; '
            'font-size:14px; min-width:200px; box-shadow:0 2px 4px rgba(34,197,94,0.1);">'
            '<span style="display:flex;align-items:center;justify-content:center;width:32px;height:32px;'
            'background:linear-gradient(135deg,#22c55e,#16a34a);border-radius:8px;">'
            '<i class="fas fa-tag" style="color:#fff;font-size:14px;"></i></span>'
            '<span>{}</span></div>',
            obj.name
        )

    @admin.display(description='عدد الموظفين')
    def employees_count(self, obj):
        from django.utils.html import format_html
        from apps.core.models import EmployeeFile
        count = EmployeeFile.objects.filter(cost_center=obj).count()
        if count > 0:
            return format_html(
                '<span style="display:inline-flex;align-items:center;justify-content:center;'
                'padding:6px 14px;background:#ecfdf5;border-radius:20px;font-weight:700;'
                'color:#059669;font-size:13px;min-width:50px;">'
                '<i class="fas fa-users" style="margin-left:6px;"></i>{}</span>',
                count
            )
        return format_html('<span style="color:#9ca3af;font-size:12px;">لا يوجد</span>')

    @admin.display(description='تاريخ الإنشاء', ordering='created_at')
    def created_at_display(self, obj):
        from django.utils.html import format_html
        if obj.created_at:
            return format_html(
                '<span style="color:#64748b;font-size:12px;">'
                '<i class="fas fa-calendar-alt" style="margin-left:4px;"></i>{}</span>',
                obj.created_at.strftime('%Y-%m-%d')
            )
        return '-'


@admin.register(OrganizationProxy)
class OrganizationProxyAdmin(admin.ModelAdmin):
    """إدارة المؤسسات"""
    list_display = ('id', 'name_display', 'created_at_display')
    search_fields = ('name',)
    ordering = ('name',)
    list_per_page = 25

    @admin.display(description='اسم المؤسسة', ordering='name')
    def name_display(self, obj):
        from django.utils.html import format_html
        return format_html(
            '<div style="display:inline-flex; align-items:center; gap:10px; padding:8px 18px; '
            'background:linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); '
            'border:1px solid #fcd34d; border-radius:12px; font-weight:700; color:#92400e; '
            'font-size:14px; min-width:200px; box-shadow:0 2px 4px rgba(245,158,11,0.1);">'
            '<span style="display:flex;align-items:center;justify-content:center;width:32px;height:32px;'
            'background:linear-gradient(135deg,#f59e0b,#d97706);border-radius:8px;">'
            '<i class="fas fa-city" style="color:#fff;font-size:14px;"></i></span>'
            '<span>{}</span></div>',
            obj.name
        )

    @admin.display(description='تاريخ الإنشاء', ordering='created_at')
    def created_at_display(self, obj):
        from django.utils.html import format_html
        if obj.created_at:
            return format_html(
                '<span style="color:#64748b;font-size:12px;">'
                '<i class="fas fa-calendar-alt" style="margin-left:4px;"></i>{}</span>',
                obj.created_at.strftime('%Y-%m-%d')
            )
        return '-'


@admin.register(SponsorshipProxy)
class SponsorshipProxyAdmin(admin.ModelAdmin):
    """إدارة الكفالات"""
    list_display = ('id', 'name_display', 'created_at_display')
    search_fields = ('name',)
    ordering = ('name',)
    list_per_page = 25

    @admin.display(description='اسم الكفالة', ordering='name')
    def name_display(self, obj):
        from django.utils.html import format_html
        return format_html(
            '<div style="display:inline-flex; align-items:center; gap:10px; padding:8px 18px; '
            'background:linear-gradient(135deg, #fce7f3 0%, #fbcfe8 100%); '
            'border:1px solid #f9a8d4; border-radius:12px; font-weight:700; color:#9d174d; '
            'font-size:14px; min-width:200px; box-shadow:0 2px 4px rgba(236,72,153,0.1);">'
            '<span style="display:flex;align-items:center;justify-content:center;width:32px;height:32px;'
            'background:linear-gradient(135deg,#ec4899,#db2777);border-radius:8px;">'
            '<i class="fas fa-handshake" style="color:#fff;font-size:14px;"></i></span>'
            '<span>{}</span></div>',
            obj.name
        )

    @admin.display(description='تاريخ الإنشاء', ordering='created_at')
    def created_at_display(self, obj):
        from django.utils.html import format_html
        if obj.created_at:
            return format_html(
                '<span style="color:#64748b;font-size:12px;">'
                '<i class="fas fa-calendar-alt" style="margin-left:4px;"></i>{}</span>',
                obj.created_at.strftime('%Y-%m-%d')
            )
        return '-'


@admin.register(UserMessageProxy)
class UserMessageProxyAdmin(admin.ModelAdmin):
    """إدارة الرسائل بين الموظفين والمديرين"""
    list_display = ('id', 'status_display', 'sender_display', 'receiver_display', 'message_preview', 'has_reply', 'sent_at_display')
    list_filter = ('status', 'sent_at', 'sender__branch', 'receiver__branch')
    search_fields = ('sender__username', 'sender__first_name', 'receiver__username', 'receiver__first_name', 'message_text')
    ordering = ('-sent_at',)
    list_per_page = 25
    autocomplete_fields = ['sender', 'receiver', 'reply_by']
    
    class Media:
        css = {
            'all': ('css/admin_custom.css',)
        }
    
    fieldsets = (
        ('الرسالة', {
            'fields': ('sender', 'receiver', 'message_text', 'sent_at'),
            'classes': ('wide',),
        }),
        ('الرد', {
            'fields': ('status', 'reply_text', 'reply_by', 'reply_at', 'reply_file_path'),
            'classes': ('wide', 'collapse'),
        }),
    )
    
    readonly_fields = ('sent_at', 'reply_at')
    
    def get_readonly_fields(self, request, obj=None):
        """المرسل والمستقبل للقراءة فقط بعد الإنشاء"""
        if obj:
            return self.readonly_fields + ('sender', 'receiver', 'message_text')
        return self.readonly_fields
    
    def save_model(self, request, obj, form, change):
        """تعيين المرسل تلقائياً عند الإنشاء"""
        if not change:
            obj.sender = request.user
        # تعيين reply_by و reply_at عند الرد
        if change and obj.reply_text and not obj.reply_by:
            obj.reply_by = request.user
            obj.reply_at = timezone.now()
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        """تصفية الرسائل حسب صلاحيات المستخدم"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        
        user_groups = list(request.user.groups.values_list('name', flat=True))
        
        # مدير الموارد ومدير الأدمن يرون جميع الرسائل
        if 'مدير الموارد' in user_groups or 'مدير الأدمن' in user_groups:
            return qs
        
        # باقي المستخدمين يرون رسائلهم فقط (المرسلة والمستقبلة)
        return qs.filter(
            models.Q(sender=request.user) | models.Q(receiver=request.user)
        )
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """تحديد المستقبل - يظهر جميع المستخدمين للمديرين، وفرع المستخدم للموظفين"""
        if db_field.name == 'receiver':
            from apps.core.models import User
            user_groups = list(request.user.groups.values_list('name', flat=True))
            
            if 'موظف فرع' in user_groups or 'مدير فرع' in user_groups:
                # الموظف يرسل للمديرين فقط
                kwargs['queryset'] = User.objects.filter(
                    is_staff=True,
                    groups__name__in=['مدير فرع', 'مدير الموارد', 'مدير الأدمن']
                ).distinct()
            else:
                kwargs['queryset'] = User.objects.filter(is_staff=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description='الحالة', ordering='status')
    def status_display(self, obj):
        from django.utils.html import format_html
        if obj.status == 'closed':
            return format_html(
                '<span style="display:inline-flex;align-items:center;padding:5px 12px;'
                'background:#dcfce7;border-radius:20px;font-weight:600;color:#166534;font-size:12px;">'
                '<i class="fas fa-check-circle" style="margin-left:5px;"></i>مغلقة</span>'
            )
        return format_html(
            '<span style="display:inline-flex;align-items:center;padding:5px 12px;'
            'background:#fef3c7;border-radius:20px;font-weight:600;color:#92400e;font-size:12px;">'
            '<i class="fas fa-clock" style="margin-left:5px;"></i>مفتوحة</span>'
        )

    @admin.display(description='المرسل', ordering='sender')
    def sender_display(self, obj):
        from django.utils.html import format_html
        return format_html(
            '<span style="display:inline-flex;align-items:center;gap:6px;padding:5px 12px;'
            'background:#eff6ff;border-radius:8px;color:#1e40af;font-weight:600;font-size:13px;">'
            '<i class="fas fa-user"></i>{}</span>',
            obj.sender.get_full_name() or obj.sender.username
        )

    @admin.display(description='المستقبل', ordering='receiver')
    def receiver_display(self, obj):
        from django.utils.html import format_html
        return format_html(
            '<span style="display:inline-flex;align-items:center;gap:6px;padding:5px 12px;'
            'background:#f0fdf4;border-radius:8px;color:#166534;font-weight:600;font-size:13px;">'
            '<i class="fas fa-user"></i>{}</span>',
            obj.receiver.get_full_name() or obj.receiver.username
        )

    @admin.display(description='الرسالة')
    def message_preview(self, obj):
        from django.utils.html import format_html
        text = obj.message_text[:80] + '...' if len(obj.message_text) > 80 else obj.message_text
        return format_html(
            '<div style="max-width:300px;font-size:13px;color:#475569;line-height:1.5;">{}</div>',
            text
        )
    
    @admin.display(description='رد', boolean=True)
    def has_reply(self, obj):
        return bool(obj.reply_text)

    @admin.display(description='تاريخ الإرسال', ordering='sent_at')
    def sent_at_display(self, obj):
        from django.utils.html import format_html
        if obj.sent_at:
            return format_html(
                '<span style="color:#64748b;font-size:12px;">'
                '<i class="fas fa-calendar" style="margin-left:4px;"></i>{}</span>',
                obj.sent_at.strftime('%Y-%m-%d %H:%M')
            )
        return '-'
    
    # إجراءات جماعية
    @admin.action(description='✓ تحديد كمغلقة')
    def mark_closed(self, request, queryset):
        queryset.update(status='closed')
        self.message_user(request, f'تم إغلاق {queryset.count()} رسالة')
    
    @admin.action(description='○ إعادة فتح')
    def mark_open(self, request, queryset):
        queryset.update(status='open')
        self.message_user(request, f'تم فتح {queryset.count()} رسالة')
    
    actions = ['mark_closed', 'mark_open']
