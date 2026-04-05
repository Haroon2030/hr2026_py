"""
أمر إدارة: تصفير البدلات لجميع الموظفين
==========================================
يُبقي فقط الراتب الأساسي كما هو في قاعدة البيانات،
ويصفّر: بدل السكن، بدل النقل، البدلات الأخرى في ملفات الموظفين وكشوف الرواتب المسودة.

الاستخدام:
    python manage.py reset_allowances
"""
from django.core.management.base import BaseCommand
from django.db import transaction, models
from apps.core.models import EmployeeFile, Payroll, PayrollStatusChoices


class Command(BaseCommand):
    help = "تصفير بدل السكن والنقل والبدلات الأخرى لجميع الموظفين وكشوف الرواتب"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='معاينة التغييرات بدون تطبيقها على قاعدة البيانات',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # جلب الموظفين الذين لديهم أي بدل غير صفر في ملف الموظف
        employees_to_update = EmployeeFile.objects.filter(
            models.Q(housing_allowance__gt=0) | 
            models.Q(transport_allowance__gt=0) | 
            models.Q(other_allowances__gt=0)
        )
        emp_count = employees_to_update.count()

        # جلب كشوف الرواتب التي لديها بدلات (المسودات فقط)
        payrolls_to_update = Payroll.objects.filter(
            status=PayrollStatusChoices.DRAFT
        ).filter(
            models.Q(housing_allowance__gt=0) | 
            models.Q(transport_allowance__gt=0) | 
            models.Q(other_allowances__gt=0) |
            models.Q(overtime_amount__gt=0)
        )
        payroll_count = payrolls_to_update.count()

        if emp_count == 0 and payroll_count == 0:
            self.stdout.write(self.style.SUCCESS(
                "DONE: All allowances in EmployeeFiles and Draft Payrolls are already zeroed."
            ))
            return

        # عرض تفاصيل قبل التطبيق
        self.stdout.write(self.style.WARNING(
            f"\n{'[PREVIEW ONLY] ' if dry_run else ''}Will reset:\n"
            f"  • {emp_count} Employee profile allowances\n"
            f"  • {payroll_count} Draft payroll record allowances\n"
        ))

        if dry_run:
            self.stdout.write(self.style.WARNING(
                "\nWARNING: Preview mode - no changes applied.\n"
            ))
            return

        # تطبيق التحديث بشكل ذري
        with transaction.atomic():
            if emp_count > 0:
                employees_to_update.update(
                    housing_allowance=0,
                    transport_allowance=0,
                    other_allowances=0,
                )
            
            if payroll_count > 0:
                # نستخدم حلقة لضمان إعادة حساب الصافي لكل كشف
                for p in payrolls_to_update:
                    p.housing_allowance = 0
                    p.transport_allowance = 0
                    p.other_allowances = 0
                    p.overtime_amount = 0
                    p.overtime_hours = 0
                    p.calculate_net_salary()
                    p.save()

        self.stdout.write(self.style.SUCCESS(
            f"\nDONE: Successfully reset allowances in {emp_count} profiles and {payroll_count} payrolls."
            f"\nBasic salary for each employee remains unchanged.\n"
        ))
