"""
أمر إعداد المجموعات والصلاحيات
================================
ينشئ مجموعات Django مع صلاحيات مناسبة للأدوار المختلفة
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType


class Command(BaseCommand):
    help = 'إعداد مجموعات المستخدمين والصلاحيات'

    def handle(self, *args, **options):
        self.stdout.write('جاري إعداد المجموعات والصلاحيات...')

        # تعريف المجموعات وصلاحياتها
        groups_config = {
            'مدير عام': {
                'description': 'جميع الصلاحيات',
                'models': '__all__',
            },
            'مدير فرع': {
                'description': 'إدارة الموظفين والطلبات في الفرع',
                'models': {
                    'employeefile': ['view', 'add', 'change'],
                    'advancefile': ['view', 'add', 'change'],
                    'statementfile': ['view', 'add', 'change'],
                    'violationfile': ['view', 'add', 'change'],
                    'terminationfile': ['view', 'add', 'change'],
                    'medicalinsurance': ['view', 'add', 'change'],
                    'medicalexcuse': ['view', 'add', 'change'],
                    'salaryadjustment': ['view'],
                    'attendancerecord': ['view', 'add', 'change'],
                    'employeetransferrequest': ['view', 'add', 'change'],
                    'notification': ['view', 'change'],
                    'performancereview': ['view', 'add', 'change'],
                },
            },
            'مدير إدارة': {
                'description': 'إدارة الطلبات في القسم',
                'models': {
                    'employeefile': ['view', 'change'],
                    'advancefile': ['view', 'change'],
                    'statementfile': ['view', 'change'],
                    'violationfile': ['view', 'change'],
                    'terminationfile': ['view', 'change'],
                    'medicalinsurance': ['view', 'change'],
                    'medicalexcuse': ['view', 'change'],
                    'salaryadjustment': ['view'],
                    'attendancerecord': ['view', 'change'],
                    'employeetransferrequest': ['view', 'change'],
                    'notification': ['view'],
                    'performancereview': ['view', 'add', 'change'],
                },
            },
            'محاسب': {
                'description': 'إدارة الرواتب والسلف',
                'models': {
                    'employeefile': ['view'],
                    'advancefile': ['view', 'add', 'change'],
                    'salaryadjustment': ['view', 'add', 'change'],
                    'payroll': ['view', 'add', 'change', 'delete'],
                    'departmentmodel': ['view'],
                    'attendancerecord': ['view'],
                    'notification': ['view'],
                },
            },
            'موارد بشرية': {
                'description': 'إدارة شؤون الموظفين',
                'models': {
                    'employeefile': ['view', 'add', 'change', 'delete'],
                    'advancefile': ['view', 'add', 'change'],
                    'statementfile': ['view', 'add', 'change'],
                    'violationfile': ['view', 'add', 'change'],
                    'terminationfile': ['view', 'add', 'change'],
                    'medicalinsurance': ['view', 'add', 'change'],
                    'medicalexcuse': ['view', 'add', 'change'],
                    'salaryadjustment': ['view', 'add', 'change'],
                    'attendancerecord': ['view', 'add', 'change', 'delete'],
                    'employeetransferrequest': ['view', 'add', 'change'],
                    'departmentmodel': ['view', 'add', 'change'],
                    'payroll': ['view', 'add', 'change'],
                    'performancereview': ['view', 'add', 'change'],
                    'notification': ['view', 'add', 'change'],
                    'systemmessage': ['view', 'add', 'change'],
                },
            },
            'موظف': {
                'description': 'عرض البيانات الخاصة فقط',
                'models': {
                    'employeefile': ['view'],
                    'advancefile': ['view', 'add'],
                    'statementfile': ['view', 'add'],
                    'medicalexcuse': ['view', 'add'],
                    'notification': ['view', 'change'],
                    'performancereview': ['view'],
                },
            },
        }

        app_label = 'hr'

        for group_name, config in groups_config.items():
            group, created = Group.objects.get_or_create(name=group_name)
            action = 'إنشاء' if created else 'تحديث'
            self.stdout.write(f'  {action} مجموعة: {group_name}')

            # مسح الصلاحيات الحالية لإعادة تعيينها
            group.permissions.clear()

            if config['models'] == '__all__':
                # جميع صلاحيات التطبيق
                perms = Permission.objects.filter(
                    content_type__app_label=app_label
                )
                group.permissions.set(perms)
                self.stdout.write(
                    self.style.SUCCESS(f'    ← {perms.count()} صلاحية')
                )
            else:
                count = 0
                for model_name, actions in config['models'].items():
                    try:
                        ct = ContentType.objects.get(
                            app_label=app_label, model=model_name
                        )
                        for action_name in actions:
                            codename = f'{action_name}_{model_name}'
                            try:
                                perm = Permission.objects.get(
                                    content_type=ct, codename=codename
                                )
                                group.permissions.add(perm)
                                count += 1
                            except Permission.DoesNotExist:
                                self.stdout.write(
                                    self.style.WARNING(
                                        f'    ⚠ صلاحية غير موجودة: {codename}'
                                    )
                                )
                    except ContentType.DoesNotExist:
                        self.stdout.write(
                            self.style.WARNING(
                                f'    ⚠ نموذج غير موجود: {model_name}'
                            )
                        )
                self.stdout.write(
                    self.style.SUCCESS(f'    ← {count} صلاحية')
                )

        self.stdout.write(self.style.SUCCESS('\n✅ تم إعداد المجموعات والصلاحيات بنجاح!'))
