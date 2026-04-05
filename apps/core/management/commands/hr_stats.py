"""
أمر عرض إحصائيات النظام
=========================
يعرض ملخص شامل لجميع بيانات النظام
الاستخدام: python manage.py hr_stats
"""

from django.core.management.base import BaseCommand
from django.db.models import Count, Sum, Q

from apps.core.models import (
    User, EmployeeFile, AdvanceFile, StatementFile,
    ViolationFile, TerminationFile, MedicalInsurance,
    MedicalExcuse, SalaryAdjustment, EmployeeTransferRequest,
    AttendanceRecord, Notification, ActivityLog,
)


class Command(BaseCommand):
    help = 'عرض إحصائيات شاملة للنظام'

    def handle(self, *args, **options):
        self.stdout.write('\n' + '='*60)
        self.stdout.write('📊 إحصائيات نظام الموارد البشرية - HR Pro')
        self.stdout.write('='*60)

        # إحصائيات المستخدمين
        total_users = User.objects.count()
        active_users = User.objects.filter(is_active=True).count()
        roles = User.objects.values('role').annotate(count=Count('id'))
        self.stdout.write(f'\n👥 المستخدمون: {total_users} (نشط: {active_users})')
        for r in roles:
            self.stdout.write(f'   - {r["role"]}: {r["count"]}')

        # إحصائيات كل نموذج
        models_info = [
            ('📁 ملفات الموظفين', EmployeeFile),
            ('💰 طلبات السلف', AdvanceFile),
            ('📝 الإفادات/الإجازات', StatementFile),
            ('⚠️ المخالفات', ViolationFile),
            ('🚪 إنهاءات الخدمات', TerminationFile),
            ('🏥 التأمين الطبي', MedicalInsurance),
            ('🩺 الأعذار الطبية', MedicalExcuse),
            ('💵 تعديلات الرواتب', SalaryAdjustment),
            ('🔄 طلبات النقل', EmployeeTransferRequest),
            ('⏰ سجلات الحضور', AttendanceRecord),
        ]

        self.stdout.write(f'\n{"─"*60}')
        for label, model in models_info:
            total = model.objects.count()
            try:
                pending = model.objects.filter(status='pending').count()
                approved = model.objects.filter(
                    Q(status='approved') | Q(status='completed')
                ).count()
                self.stdout.write(
                    f'{label}: {total} (معلّق: {pending}, مكتمل: {approved})'
                )
            except Exception:
                self.stdout.write(f'{label}: {total}')

        # إحصائيات إضافية
        self.stdout.write(f'\n{"─"*60}')
        self.stdout.write(f'🔔 الإشعارات: {Notification.objects.count()}')
        self.stdout.write(
            f'   غير مقروءة: {Notification.objects.filter(is_read=False).count()}'
        )
        self.stdout.write(f'📋 سجل النشاطات: {ActivityLog.objects.count()}')

        # إحصائيات الرواتب
        salary_stats = SalaryAdjustment.objects.aggregate(
            total_increase=Sum('salary_increase'),
            total_adjustments=Count('id'),
        )
        if salary_stats['total_increase']:
            self.stdout.write(
                f'\n💵 إجمالي زيادات الرواتب: {salary_stats["total_increase"]:,.2f} ر.س'
                f' ({salary_stats["total_adjustments"]} تعديل)'
            )

        # إحصائيات السلف
        advance_stats = AdvanceFile.objects.aggregate(
            total_amount=Sum('advance_amount'),
            total_count=Count('id'),
        )
        if advance_stats['total_amount']:
            self.stdout.write(
                f'💰 إجمالي السلف: {advance_stats["total_amount"]:,.2f} ر.س'
                f' ({advance_stats["total_count"]} طلب)'
            )

        self.stdout.write('\n' + '='*60 + '\n')
