"""
فلاتر قالب مخصصة لنظام الموارد البشرية
"""
from django import template

register = template.Library()


_MODEL_ICONS = {
    # ─── إدارة المستخدمين والصلاحيات ───────────────────────────
    'User':                     'fas fa-user-lock',
    'UserProxy':                'fas fa-user-lock',
    'Group':                    'fas fa-layer-group',

    # ─── الموظفون ────────────────────────────────────────────────
    'EmployeeFile':             'fas fa-id-badge',
    'EmployeeFileProxy':        'fas fa-id-badge',

    # ─── الإجازات ────────────────────────────────────────────────
    'StatementFile':            'fas fa-calendar-alt',
    'StatementFileProxy':       'fas fa-calendar-alt',

    # ─── السلف ───────────────────────────────────────────────────
    'AdvanceFile':              'fas fa-hand-holding-usd',
    'AdvanceFileProxy':         'fas fa-hand-holding-usd',

    # ─── المخالفات ───────────────────────────────────────────────
    'ViolationFile':            'fas fa-exclamation-circle',
    'ViolationFileProxy':       'fas fa-exclamation-circle',

    # ─── إنهاء الخدمة ───────────────────────────────────────────
    'TerminationFile':          'fas fa-user-slash',
    'TerminationFileProxy':     'fas fa-user-slash',

    # ─── التأمين الطبي والإعذارات ─────────────────────────────
    'MedicalInsurance':         'fas fa-shield-virus',
    'MedicalInsuranceProxy':    'fas fa-shield-virus',
    'MedicalExcuse':            'fas fa-file-medical',
    'MedicalExcuseProxy':       'fas fa-file-medical',

    # ─── تعديل الرواتب ──────────────────────────────────────────
    'SalaryAdjustment':         'fas fa-sliders-h',
    'SalaryAdjustmentProxy':    'fas fa-sliders-h',

    # ─── طلبات النقل ────────────────────────────────────────────
    'EmployeeTransferRequest':      'fas fa-people-arrows',
    'EmployeeTransferRequestProxy': 'fas fa-people-arrows',

    # ─── الحضور ─────────────────────────────────────────────────
    'AttendanceRecord':         'fas fa-fingerprint',
    'AttendanceRecordProxy':    'fas fa-fingerprint',

    # ─── كشوف الرواتب ───────────────────────────────────────────
    'Payroll':                  'fas fa-file-invoice-dollar',
    'PayrollProxy':             'fas fa-file-invoice-dollar',
    'PayrollPeriod':            'fas fa-calendar-week',
    'FinanceSettings':          'fas fa-percent',

    # ─── تقييم الأداء ───────────────────────────────────────────
    'PerformanceReview':        'fas fa-star-half-alt',
    'PerformanceReviewProxy':   'fas fa-star-half-alt',

    # ─── الأقسام ────────────────────────────────────────────────
    'DepartmentModel':          'fas fa-sitemap',
    'DepartmentModelProxy':     'fas fa-sitemap',

    # ─── الفروع ─────────────────────────────────────────────────
    'BranchProxy':              'fas fa-map-marked-alt',

    # ─── مراكز التكلفة ──────────────────────────────────────────
    'CostCenterProxy':          'fas fa-tags',

    # ─── الرسائل والإشعارات والتتبع ─────────────────────────────
    'SystemMessage':            'fas fa-envelope-open-text',
    'SystemMessageProxy':       'fas fa-envelope-open-text',
    'Notification':             'fas fa-bell',
    'NotificationProxy':        'fas fa-bell',
    'ActivityLog':              'fas fa-clipboard-list',
    'ActivityLogProxy':         'fas fa-clipboard-list',
}

_APP_ICONS = {
    'core':         'fas fa-users-cog',
    'requests':     'fas fa-briefcase',
    'system':       'fas fa-cog',
    'payroll':      'fas fa-coins',
    'auth':         'fas fa-shield-alt',
}


@register.filter
def model_icon(object_name):
    """Return a Font Awesome icon class for a given Django model object_name."""
    return _MODEL_ICONS.get(str(object_name), 'fas fa-circle-dot')


@register.filter
def app_icon(app_label):
    """Return a Font Awesome icon class for a given Django app_label."""
    return _APP_ICONS.get(str(app_label), 'fas fa-folder')




@register.filter
def approval_badge(value):
    """عرض حالة الاعتماد كشارة ملونة"""
    badges = {
        'pending': '<span class="badge badge-warning">معلّق</span>',
        'approved': '<span class="badge badge-success">معتمد</span>',
        'rejected': '<span class="badge badge-danger">مرفوض</span>',
    }
    from django.utils.safestring import mark_safe
    return mark_safe(badges.get(value, value))


@register.filter
def status_badge(value):
    """عرض حالة الطلب كشارة ملونة"""
    badges = {
        'pending': '<span class="badge badge-warning">معلّق</span>',
        'in_progress': '<span class="badge badge-info">قيد المعالجة</span>',
        'completed': '<span class="badge badge-success">مكتمل</span>',
        'approved': '<span class="badge badge-success">معتمد</span>',
        'rejected': '<span class="badge badge-danger">مرفوض</span>',
    }
    from django.utils.safestring import mark_safe
    return mark_safe(badges.get(value, value))
