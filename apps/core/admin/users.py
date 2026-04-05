"""
إدارة المستخدمين / User Admin
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html

from apps.core.models import User


class UserAdmin(BaseUserAdmin):
    """
    إدارة المستخدمين - تشمل إدارة الأدوار والفروع والصلاحيات
    """
    list_display = (
        'username', 'get_full_name_display', 'email', 'role_badge',
        'branch', 'department', 'is_active', 'date_joined'
    )
    list_filter = ('role', 'is_active', 'department', 'branch', 'is_staff')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'phone')
    list_editable = ('is_active',)
    list_per_page = 25
    ordering = ('-date_joined',)

    fieldsets = (
        ('بيانات الدخول', {
            'fields': ('username', 'password')
        }),
        ('البيانات الشخصية', {
            'fields': ('first_name', 'last_name', 'email', 'phone')
        }),
        ('الوظيفة والدور', {
            'fields': ('role', 'branch', 'department'),
            'description': 'حدد دور المستخدم والفرع والإدارة التابع لها'
        }),
        ('الصلاحيات', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',),
        }),
        ('التواريخ', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',),
        }),
    )

    add_fieldsets = (
        ('بيانات المستخدم الجديد', {
            'classes': ('wide',),
            'fields': (
                'username', 'password1', 'password2',
                'first_name', 'last_name', 'email', 'phone',
                'role', 'branch', 'department', 'is_active', 'is_staff'
            ),
        }),
    )

    @admin.display(description='الاسم الكامل')
    def get_full_name_display(self, obj):
        return obj.get_full_name() or obj.username

    @admin.display(description='الدور')
    def role_badge(self, obj):
        """عرض الدور بشكل مميز بلون خاص"""
        colors = {
            'admin':               '#dc3545',
            'manager':             '#fd7e14',
            'branch_manager':      '#28a745',
            'branch':              '#17a2b8',
            'department_manager':  '#6f42c1',
            'department_employee': '#20c997',
            'employee':            '#6c757d',
        }
        color = colors.get(obj.role, '#6c757d')
        return format_html(
            '<span style="background:{}; color:#fff; padding:3px 10px; '
            'border-radius:12px; font-size:11px;">{}</span>',
            color, obj.get_role_display()
        )


class _UserAutocompleteAdmin(UserAdmin):
    """
    تسجيل مخفي لـ User يتيح autocomplete دون ظهور القسم في الشريط الجانبي.
    يُستخدم من قِبَل نماذج proxy الأخرى التي لها ForeignKey إلى User.
    """
    def get_model_perms(self, request):
        return {}


admin.site.register(User, _UserAutocompleteAdmin)
