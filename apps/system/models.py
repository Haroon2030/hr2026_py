"""
نماذج Proxy لتجميع شاشات إدارة النظام في قسم منفصل بالشريط الجانبي.
لا تُنشئ جداول جديدة - تستخدم نفس جداول تطبيق hr.
"""
from apps.core.models import (
    User,
    DepartmentModel,
    PerformanceReview,
    SystemMessage,
    Notification,
    ActivityLog,
    Branch,
    CostCenter,
    Organization,
    Sponsorship,
    UserMessage,
)


class UserProxy(User):
    class Meta:
        proxy = True
        verbose_name = 'مستخدم'
        verbose_name_plural = 'المستخدمون'
        app_label = 'system'


class DepartmentModelProxy(DepartmentModel):
    class Meta:
        proxy = True
        verbose_name = 'قسم / إدارة'
        verbose_name_plural = 'الأقسام والإدارات'
        app_label = 'system'


class PerformanceReviewProxy(PerformanceReview):
    class Meta:
        proxy = True
        verbose_name = 'تقييم أداء'
        verbose_name_plural = 'تقييمات الأداء'
        app_label = 'system'


class SystemMessageProxy(SystemMessage):
    class Meta:
        proxy = True
        verbose_name = 'رسالة نظام'
        verbose_name_plural = 'رسائل النظام'
        app_label = 'system'


class NotificationProxy(Notification):
    class Meta:
        proxy = True
        verbose_name = 'إشعار'
        verbose_name_plural = 'الإشعارات'
        app_label = 'system'


class ActivityLogProxy(ActivityLog):
    class Meta:
        proxy = True
        verbose_name = 'سجل نشاط'
        verbose_name_plural = 'سجل النشاطات'
        app_label = 'system'


class BranchProxy(Branch):
    class Meta:
        proxy = True
        verbose_name = 'فرع'
        verbose_name_plural = 'الفروع'
        app_label = 'system'


class CostCenterProxy(CostCenter):
    class Meta:
        proxy = True
        verbose_name = 'مركز تكلفة'
        verbose_name_plural = 'مراكز التكلفة'
        app_label = 'system'


class OrganizationProxy(Organization):
    class Meta:
        proxy = True
        verbose_name = 'مؤسسة'
        verbose_name_plural = 'المؤسسات'
        app_label = 'system'


class SponsorshipProxy(Sponsorship):
    class Meta:
        proxy = True
        verbose_name = 'كفالة'
        verbose_name_plural = 'الكفالات'
        app_label = 'system'


class UserMessageProxy(UserMessage):
    class Meta:
        proxy = True
        verbose_name = 'رسالة'
        verbose_name_plural = 'الرسائل'
        app_label = 'system'
