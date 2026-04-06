"""
HR Pro URL Configuration
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

# Redirects for models moved from hr → employee_ops
_MOVED_MODELS = {
    'employeefile':            'employeefileproxy',
    'advancefile':             'advancefileproxy',
    'terminationfile':         'terminationfileproxy',
    'salaryadjustment':        'salaryadjustmentproxy',
    'employeetransferrequest': 'employeetransferrequestproxy',
    'medicalinsurance':        'medicalinsuranceproxy',
    'medicalexcuse':           'medicalexcuseproxy',
}

# Redirects from old app names to new app names
_APP_RENAMES = {
    'hr': 'core',
    'employee_ops': 'requests',
    'hr_system': 'system',
    'finance': 'payroll',
}

def _make_redirect_view(target_url_pattern):
    """Factory to avoid lambda late-binding issue in loops."""
    def view(request, rest=''):
        return RedirectView.as_view(
            url=target_url_pattern.format(rest=rest),
            permanent=True,
        )(request)
    return view

redirect_patterns = []

# Redirect old app URLs to new app URLs
for old_app, new_app in _APP_RENAMES.items():
    redirect_patterns.append(
        re_path(
            rf'^{old_app}/(?P<rest>.*)$',
            _make_redirect_view(f'/{new_app}/{{rest}}'),
        )
    )

# Model-level redirects within apps (core → requests)
for old, new in _MOVED_MODELS.items():
    redirect_patterns.append(
        re_path(
            rf'^core/{old}/(?P<rest>.*)$',
            _make_redirect_view(f'/requests/{new}/{{rest}}'),
        )
    )

# خدمة ملفات الوسائط والثابتة في بيئة التطوير (يجب أن تكون قبل admin)
_media_patterns = []
if settings.DEBUG:
    _media_patterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # خدمة الملفات الثابتة من المصدر مباشرة (بدون collectstatic)
    _media_patterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])

urlpatterns = _media_patterns + redirect_patterns + [
    path('i18n/', include('django.conf.urls.i18n')),
    path('', admin.site.urls),  # لوحة الإدارة هي الصفحة الرئيسية
]
