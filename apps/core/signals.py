"""
إشارات Django لتسجيل النشاطات وإرسال الإشعارات تلقائياً
==========================================================
يسجل جميع عمليات الإنشاء والتعديل والحذف في سجل النشاطات
ينشئ إشعارات للمستخدمين عند اعتماد/رفض الطلبات
"""

import logging
from django.db.models.signals import post_save, post_delete, pre_save
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from .models import (
    ActivityLog, Notification,
    EmployeeFile, AdvanceFile, StatementFile,
    ViolationFile, TerminationFile, MedicalInsurance,
    MedicalExcuse, SalaryAdjustment, EmployeeTransferRequest,
    AttendanceRecord, Payroll, PerformanceReview,
    ApprovalStatus, WorkerStatusLog,
)

logger = logging.getLogger(__name__)

# النماذج التي يتم تتبعها
TRACKED_MODELS = {
    EmployeeFile: 'employees',
    AdvanceFile: 'advances',
    StatementFile: 'statements',
    ViolationFile: 'violations',
    TerminationFile: 'terminations',
    MedicalInsurance: 'medical_insurance',
    MedicalExcuse: 'medical_excuses',
    SalaryAdjustment: 'salary_adjustments',
    EmployeeTransferRequest: 'transfers',
    AttendanceRecord: 'attendance',
    Payroll: 'payroll',
    PerformanceReview: 'performance',
}

# النماذج التي تدعم سلسلة الاعتمادات (لديها BaseRequest)
# AttendanceRecord مُضاف بعد إصلاح وراثته من BaseRequest
APPROVAL_MODELS = {
    EmployeeFile, AdvanceFile, StatementFile,
    ViolationFile, TerminationFile, MedicalInsurance,
    MedicalExcuse, SalaryAdjustment, EmployeeTransferRequest,
    AttendanceRecord,
}

# تخزين حالة الاعتماد السابقة قبل الحفظ
_pre_save_approval_state = {}


def _log_activity(action, module, instance, user=None, description=None):
    """تسجيل نشاط في سجل النشاطات"""
    try:
        username = ''
        if user:
            username = user.username
        elif hasattr(instance, 'uploaded_by') and instance.uploaded_by:
            username = instance.uploaded_by.username
            user = instance.uploaded_by

        ActivityLog.objects.create(
            user=user,
            username=username,
            action=action,
            module=module,
            description=description or f'{action} {module} #{instance.pk}',
            target_id=instance.pk,
        )
    except Exception as e:
        logger.warning(f'Failed to log activity: {e}')


def _create_notification(user, title, message, notification_type='info', icon='fas fa-bell'):
    """إنشاء إشعار للمستخدم"""
    try:
        if user:
            Notification.objects.create(
                user=user,
                title=title,
                message=message,
                notification_type=notification_type,
                icon=icon,
            )
    except Exception as e:
        logger.warning(f'Failed to create notification: {e}')


def _notify_approval_change(instance, field_name, old_value, new_value):
    """إرسال إشعار عند تغيير حالة الاعتماد"""
    model_name = instance.__class__._meta.verbose_name
    emp_name = getattr(instance, 'employee_name', str(instance))

    approval_labels = {
        'branch_manager_approval': 'مدير الفرع',
        'department_manager_approval': 'مدير الإدارة',
        'manager_approval': 'المدير العام',
    }
    approver_label = approval_labels.get(field_name, field_name)

    # إشعار لصاحب الطلب
    uploaded_by = getattr(instance, 'uploaded_by', None)
    if not uploaded_by:
        return

    if new_value == ApprovalStatus.APPROVED:
        _create_notification(
            uploaded_by,
            f'تم اعتماد طلبك',
            f'تم اعتماد {model_name} ({emp_name}) من قبل {approver_label}',
            notification_type='success',
            icon='fas fa-check-circle',
        )
    elif new_value == ApprovalStatus.REJECTED:
        _create_notification(
            uploaded_by,
            f'تم رفض طلبك',
            f'تم رفض {model_name} ({emp_name}) من قبل {approver_label}',
            notification_type='warning',
            icon='fas fa-times-circle',
        )


@receiver(pre_save)
def capture_approval_state(sender, instance, **kwargs):
    """حفظ حالة الاعتماد الحالية قبل التعديل"""
    if sender in APPROVAL_MODELS and instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            _pre_save_approval_state[f'{sender.__name__}_{instance.pk}'] = {
                'branch_manager_approval': old.branch_manager_approval,
                'department_manager_approval': old.department_manager_approval,
                'manager_approval': old.manager_approval,
            }
        except sender.DoesNotExist:
            pass


@receiver(post_save)
def log_model_save(sender, instance, created, **kwargs):
    """تسجيل عمليات الإنشاء والتعديل + إشعارات الاعتماد"""
    if sender in TRACKED_MODELS:
        module = TRACKED_MODELS[sender]
        action = 'create' if created else 'update'
        name = getattr(instance, 'employee_name', str(instance))
        desc = f'{"إنشاء" if created else "تعديل"} {name}'
        _log_activity(action, module, instance, description=desc)

    # التحقق من تغيير حالة الاعتماد
    if sender in APPROVAL_MODELS and not created and instance.pk:
        key = f'{sender.__name__}_{instance.pk}'
        old_state = _pre_save_approval_state.pop(key, None)
        if old_state:
            for field in ('branch_manager_approval', 'department_manager_approval', 'manager_approval'):
                old_val = old_state.get(field)
                new_val = getattr(instance, field)
                if old_val != new_val and new_val in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED):
                    _notify_approval_change(instance, field, old_val, new_val)


@receiver(post_save, sender=Payroll)
def notify_payroll_status(sender, instance, created, **kwargs):
    """إشعار عند تحديث حالة كشف الراتب"""
    if not created and instance.employee:
        uploaded_by = getattr(instance.employee, 'uploaded_by', None)
        if instance.status == 'paid':
            _create_notification(
                uploaded_by,
                'تم صرف الراتب',
                f'تم صرف راتب شهر {instance.period_month}/{instance.period_year}',
                notification_type='success',
                icon='fas fa-money-bill-wave',
            )


@receiver(post_save, sender=PerformanceReview)
def notify_performance_review(sender, instance, created, **kwargs):
    """إشعار عند إنشاء تقييم أداء جديد"""
    if created and instance.employee:
        uploaded_by = getattr(instance.employee, 'uploaded_by', None)
        if uploaded_by:
            _create_notification(
                uploaded_by,
                'تقييم أداء جديد',
                f'تم إنشاء تقييم أداء للفترة {instance.review_period_start} - {instance.review_period_end}',
                notification_type='info',
                icon='fas fa-chart-line',
            )


@receiver(post_delete)
def log_model_delete(sender, instance, **kwargs):
    """تسجيل عمليات الحذف"""
    if sender in TRACKED_MODELS:
        module = TRACKED_MODELS[sender]
        name = getattr(instance, 'employee_name', str(instance))
        _log_activity('delete', module, instance, description=f'حذف {name}')


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """تسجيل دخول المستخدم"""
    ip = request.META.get('REMOTE_ADDR', '') if request else ''
    ActivityLog.objects.create(
        user=user,
        username=user.username,
        action='login',
        module='users',
        description=f'تسجيل دخول: {user.get_full_name() or user.username}',
        ip_address=ip if ip else None,
        user_agent=request.META.get('HTTP_USER_AGENT', '') if request else '',
    )


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """تسجيل خروج المستخدم"""
    if user:
        ActivityLog.objects.create(
            user=user,
            username=user.username,
            action='logout',
            module='users',
            description=f'تسجيل خروج: {user.get_full_name() or user.username}',
        )


# تخزين حالة العامل السابقة قبل الحفظ
_pre_save_worker_status = {}


@receiver(pre_save, sender=EmployeeFile)
def store_previous_worker_status(sender, instance, **kwargs):
    """تخزين حالة العامل السابقة قبل الحفظ للمقارنة"""
    if instance.pk:
        try:
            old_instance = EmployeeFile.objects.get(pk=instance.pk)
            _pre_save_worker_status[instance.pk] = {
                'is_suspended': old_instance.is_suspended,
                'is_on_leave': old_instance.is_on_leave,
            }
        except EmployeeFile.DoesNotExist:
            pass


@receiver(post_save, sender=EmployeeFile)
def track_worker_status_change(sender, instance, created, **kwargs):
    """إنشاء سجل عند تغيير حالة العامل (إيقاف/إجازة)"""
    from datetime import date

    if created:
        return  # لا نتتبع عند الإنشاء الأول
    
    old_status = _pre_save_worker_status.pop(instance.pk, None)
    if not old_status:
        return
    
    # تتبع تغيير حالة الإيقاف
    if instance.is_suspended and not old_status['is_suspended']:
        # تم تفعيل الإيقاف - إنشاء سجل جديد
        WorkerStatusLog.objects.create(
            employee=instance,
            status_type='suspended',
            start_date=instance.suspended_from or date.today(),
            is_active=True,
        )
    elif not instance.is_suspended and old_status['is_suspended']:
        # تم رفع الإيقاف - إنهاء السجل النشط
        WorkerStatusLog.objects.filter(
            employee=instance,
            status_type='suspended',
            is_active=True
        ).update(is_active=False, end_date=date.today())
    
    # تتبع تغيير حالة الإجازة
    if instance.is_on_leave and not old_status['is_on_leave']:
        # تم تفعيل الإجازة - إنشاء سجل جديد
        WorkerStatusLog.objects.create(
            employee=instance,
            status_type='leave',
            start_date=instance.leave_from or date.today(),
            is_active=True,
        )
    elif not instance.is_on_leave and old_status['is_on_leave']:
        # تم إنهاء الإجازة - إنهاء السجل النشط
        WorkerStatusLog.objects.filter(
            employee=instance,
            status_type='leave',
            is_active=True
        ).update(is_active=False, end_date=date.today())
