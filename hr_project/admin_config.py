from django.contrib.admin.apps import AdminConfig


class HRAdminConfig(AdminConfig):
    """تخصيص موقع الإدارة لاستخدام لوحة المعلومات كصفحة رئيسية"""
    default_site = 'apps.core.admin_site.HRAdminSite'
