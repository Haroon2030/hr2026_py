"""
أمر إعداد المجموعات والصلاحيات المتدرجة
========================================
ينشئ 4 مجموعات رئيسية:
1. موظف فرع      - يرى بيانات فرعه فقط (قراءة)
2. مدير فرع       - يدير بيانات فرعه (قراءة + تعديل)
3. مدير الموارد    - يدير جميع البيانات
4. مدير الأدمن     - صلاحيات كاملة + إدارة النظام
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission


class Command(BaseCommand):
    help = 'إعداد مجموعات الصلاحيات المتدرجة'

    # النماذج الأساسية للموظفين
    EMPLOYEE_MODELS = [
        'employeefile',
        'advancefile',
        'statementfile',
        'violationfile',
        'terminationfile',
        'medicalinsurance',
        'medicalexcuse',
        'salaryadjustment',
        'attendancerecord',
        'employeetransferrequest',
    ]
    
    # نماذج الرواتب
    PAYROLL_MODELS = [
        'payroll',
        'payrollperiod',
        'departmentmodel',
        'financesettings',
    ]
    
    # نماذج النظام
    SYSTEM_MODELS = [
        'branch',
        'costcenter',
        'organization',
        'sponsorship',
        'systemmessage',
        'notification',
        'activitylog',
        'usermessage',
    ]

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING(
            '\n═══════════════════════════════════════════════════════'
        ))
        self.stdout.write(self.style.MIGRATE_HEADING(
            '   إعداد مجموعات الصلاحيات المتدرجة'
        ))
        self.stdout.write(self.style.MIGRATE_HEADING(
            '═══════════════════════════════════════════════════════\n'
        ))

        # تعريف المجموعات
        groups_config = {
            'موظف فرع': {
                'level': 1,
                'description': 'عرض بيانات فرعه فقط',
                'permissions': self._get_branch_employee_permissions(),
            },
            'مدير فرع': {
                'level': 2,
                'description': 'إدارة بيانات فرعه',
                'permissions': self._get_branch_manager_permissions(),
            },
            'مدير الموارد': {
                'level': 3,
                'description': 'إدارة جميع بيانات الموظفين',
                'permissions': self._get_hr_manager_permissions(),
            },
            'مدير الأدمن': {
                'level': 4,
                'description': 'صلاحيات كاملة على النظام',
                'permissions': '__all__',
            },
        }

        for group_name, config in groups_config.items():
            group, created = Group.objects.get_or_create(name=group_name)
            action = '✓ إنشاء' if created else '↻ تحديث'
            
            self.stdout.write(f'\n{action} مجموعة: {group_name}')
            self.stdout.write(f'  المستوى: {config["level"]} | {config["description"]}')
            
            # مسح الصلاحيات الحالية
            group.permissions.clear()
            
            if config['permissions'] == '__all__':
                # جميع الصلاحيات
                all_perms = Permission.objects.filter(
                    content_type__app_label__in=['core', 'requests', 'system', 'payroll']
                )
                group.permissions.set(all_perms)
                self.stdout.write(
                    self.style.SUCCESS(f'  ← {all_perms.count()} صلاحية (كاملة)')
                )
            else:
                added_count = 0
                for codename in config['permissions']:
                    try:
                        perm = Permission.objects.get(codename=codename)
                        group.permissions.add(perm)
                        added_count += 1
                    except Permission.DoesNotExist:
                        pass  # تجاهل الصلاحيات غير الموجودة
                
                self.stdout.write(
                    self.style.SUCCESS(f'  ← {added_count} صلاحية')
                )

        self.stdout.write(self.style.SUCCESS(
            '\n═══════════════════════════════════════════════════════'
        ))
        self.stdout.write(self.style.SUCCESS(
            '✓ تم إعداد المجموعات بنجاح!'
        ))
        self.stdout.write(self.style.SUCCESS(
            '═══════════════════════════════════════════════════════\n'
        ))
        
        self._print_summary()

    def _get_branch_employee_permissions(self):
        """صلاحيات موظف الفرع - قراءة فقط + إرسال رسائل"""
        perms = []
        for model in self.EMPLOYEE_MODELS:
            perms.append(f'view_{model}')
        # صلاحيات الرسائل
        perms.extend([
            'view_usermessage',
            'add_usermessage',
        ])
        return perms

    def _get_branch_manager_permissions(self):
        """صلاحيات مدير الفرع - قراءة وتعديل وإضافة + رد على الرسائل"""
        perms = []
        for model in self.EMPLOYEE_MODELS:
            perms.extend([
                f'view_{model}',
                f'add_{model}',
                f'change_{model}',
            ])
        # إضافة صلاحية عرض الرواتب
        perms.append('view_payroll')
        # صلاحيات الرسائل
        perms.extend([
            'view_usermessage',
            'add_usermessage',
            'change_usermessage',
        ])
        return perms

    def _get_hr_manager_permissions(self):
        """صلاحيات مدير الموارد - جميع العمليات على الموظفين"""
        perms = []
        # صلاحيات كاملة على بيانات الموظفين
        for model in self.EMPLOYEE_MODELS:
            perms.extend([
                f'view_{model}',
                f'add_{model}',
                f'change_{model}',
                f'delete_{model}',
            ])
        # صلاحيات الرواتب
        for model in self.PAYROLL_MODELS:
            perms.extend([
                f'view_{model}',
                f'add_{model}',
                f'change_{model}',
            ])
        # صلاحيات عرض النظام
        for model in self.SYSTEM_MODELS:
            perms.append(f'view_{model}')
        return perms

    def _print_summary(self):
        """طباعة ملخص المجموعات"""
        self.stdout.write('\nملخص المجموعات:')
        self.stdout.write('─' * 50)
        
        for group in Group.objects.all().order_by('name'):
            count = group.permissions.count()
            self.stdout.write(f'  {group.name}: {count} صلاحية')
        
        self.stdout.write('─' * 50)
        self.stdout.write(
            '\nلإضافة مستخدم إلى مجموعة:'
        )
        self.stdout.write(
            '  user.groups.add(Group.objects.get(name="مدير فرع"))'
        )
        self.stdout.write('')
