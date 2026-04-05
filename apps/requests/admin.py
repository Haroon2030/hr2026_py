"""
Admin registration for employee operations proxy models.
These inherit from the original hr admin classes.
"""
from django.contrib import admin

from apps.core.admin.employees import EmployeeFileAdmin as OriginalEmployeeAdmin, TerminationFileAdmin as OriginalTerminationAdmin
from apps.core.admin.requests import AdvanceFileAdmin as OriginalAdvanceAdmin, SalaryAdjustmentAdmin as OriginalSalaryAdmin, EmployeeTransferRequestAdmin as OriginalTransferAdmin, ViolationFileAdmin as OriginalViolationAdmin, StatementFileAdmin as OriginalStatementAdmin
from apps.core.admin.medical import MedicalInsuranceAdmin as OriginalInsuranceAdmin, MedicalExcuseAdmin as OriginalMedicalExcuseAdmin
from apps.core.admin.attendance import AttendanceRecordAdmin as OriginalAttendanceAdmin
from apps.core.admin.system import WorkerStatusLogAdmin as OriginalWorkerStatusLogAdmin
from .models import (
    AdvanceFileProxy, EmployeeFileProxy, SalaryAdjustmentProxy,
    TerminationFileProxy, EmployeeTransferRequestProxy, MedicalInsuranceProxy,
    MedicalExcuseProxy, ViolationFileProxy, AttendanceRecordProxy, StatementFileProxy,
    WorkerStatusLogProxy,
)


@admin.register(AdvanceFileProxy)
class AdvanceFileProxyAdmin(OriginalAdvanceAdmin):
    pass


@admin.register(EmployeeFileProxy)
class EmployeeFileProxyAdmin(OriginalEmployeeAdmin):
    pass


@admin.register(SalaryAdjustmentProxy)
class SalaryAdjustmentProxyAdmin(OriginalSalaryAdmin):
    pass


@admin.register(TerminationFileProxy)
class TerminationFileProxyAdmin(OriginalTerminationAdmin):
    pass


@admin.register(EmployeeTransferRequestProxy)
class EmployeeTransferRequestProxyAdmin(OriginalTransferAdmin):
    pass


@admin.register(MedicalInsuranceProxy)
class MedicalInsuranceProxyAdmin(OriginalInsuranceAdmin):
    pass


@admin.register(MedicalExcuseProxy)
class MedicalExcuseProxyAdmin(OriginalMedicalExcuseAdmin):
    pass


@admin.register(ViolationFileProxy)
class ViolationFileProxyAdmin(OriginalViolationAdmin):
    pass


@admin.register(AttendanceRecordProxy)
class AttendanceRecordProxyAdmin(OriginalAttendanceAdmin):
    pass


@admin.register(StatementFileProxy)
class StatementFileProxyAdmin(OriginalStatementAdmin):
    pass


@admin.register(WorkerStatusLogProxy)
class WorkerStatusLogProxyAdmin(OriginalWorkerStatusLogAdmin):
    pass
