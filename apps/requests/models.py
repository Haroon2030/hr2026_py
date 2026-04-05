"""
Proxy models for employee operations grouping in admin sidebar.
These models don't create new database tables - they reference the same tables
as the original hr models.
"""
from apps.core.models import (
    AdvanceFile, EmployeeFile, SalaryAdjustment,
    TerminationFile, StatementFile,
    EmployeeTransferRequest, MedicalInsurance, MedicalExcuse,
    ViolationFile, AttendanceRecord, WorkerStatusLog,
)


class AdvanceFileProxy(AdvanceFile):
    class Meta:
        proxy = True
        verbose_name = 'طلب سلفة'
        verbose_name_plural = 'السلف'
        app_label = 'requests'


class EmployeeFileProxy(EmployeeFile):
    class Meta:
        proxy = True
        verbose_name = 'إضافة موظف'
        verbose_name_plural = 'إضافة الموظفين'
        app_label = 'requests'


class SalaryAdjustmentProxy(SalaryAdjustment):
    class Meta:
        proxy = True
        verbose_name = 'تعديل راتب'
        verbose_name_plural = 'تعديلات الرواتب'
        app_label = 'requests'


class TerminationFileProxy(TerminationFile):
    class Meta:
        proxy = True
        verbose_name = 'إنهاء خدمة'
        verbose_name_plural = 'إنهاء الخدمات'
        app_label = 'requests'


class StatementFileProxy(StatementFile):
    class Meta:
        proxy = True
        verbose_name = 'إجازة'
        verbose_name_plural = 'الإجازات'
        app_label = 'requests'


class EmployeeTransferRequestProxy(EmployeeTransferRequest):
    class Meta:
        proxy = True
        verbose_name = 'طلب نقل'
        verbose_name_plural = 'طلبات النقل'
        app_label = 'requests'


class MedicalInsuranceProxy(MedicalInsurance):
    class Meta:
        proxy = True
        verbose_name = 'تأمين طبي'
        verbose_name_plural = 'التأمين الطبي'
        app_label = 'requests'


class MedicalExcuseProxy(MedicalExcuse):
    class Meta:
        proxy = True
        verbose_name = 'عذر طبي'
        verbose_name_plural = 'الأعذار الطبية'
        app_label = 'requests'


class ViolationFileProxy(ViolationFile):
    class Meta:
        proxy = True
        verbose_name = 'مخالفة'
        verbose_name_plural = 'المخالفات'
        app_label = 'requests'


class AttendanceRecordProxy(AttendanceRecord):
    class Meta:
        proxy = True
        verbose_name = 'سجل حضور'
        verbose_name_plural = 'سجلات الحضور'
        app_label = 'requests'


class WorkerStatusLogProxy(WorkerStatusLog):
    class Meta:
        proxy = True
        verbose_name = 'سجل حالة عامل'
        verbose_name_plural = 'سجل حالات العمال'
        app_label = 'requests'
