"""
أمر نقل البيانات من قاعدة MySQL القديمة (PHP) إلى Django
==========================================================
ينقل جميع الجداول والعلاقات مع الحفاظ على البيانات
الاستخدام: python manage.py migrate_from_php [--table TABLE_NAME] [--dry-run]
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction
from django.contrib.auth.hashers import make_password

from apps.core.models import (
    User, EmployeeFile, AdvanceFile, StatementFile,
    ViolationFile, TerminationFile, MedicalInsurance,
    MedicalExcuse, SalaryAdjustment, EmployeeTransferRequest,
    AttendanceRecord, SystemMessage, Notification, ActivityLog,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'نقل البيانات من قاعدة بيانات PHP/MySQL القديمة إلى Django'

    def add_arguments(self, parser):
        parser.add_argument(
            '--table', type=str, default='all',
            help='اسم الجدول المراد نقله (أو all لنقل الكل)'
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='تشغيل تجريبي بدون حفظ البيانات'
        )
        parser.add_argument(
            '--batch-size', type=int, default=500,
            help='حجم الدفعة لكل عملية إدراج (الافتراضي: 500)'
        )

    def handle(self, *args, **options):
        table = options['table']
        self.dry_run = options['dry_run']
        self.batch_size = options['batch_size']

        if self.dry_run:
            self.stdout.write(self.style.WARNING('🔄 تشغيل تجريبي - لن يتم حفظ البيانات'))

        # التحقق من اتصال قاعدة البيانات القديمة
        try:
            legacy_conn = connections['legacy']
            legacy_conn.ensure_connection()
            self.stdout.write(self.style.SUCCESS('✅ تم الاتصال بقاعدة البيانات القديمة'))
        except Exception as e:
            raise CommandError(f'❌ فشل الاتصال بقاعدة البيانات القديمة: {e}')

        # خريطة الجداول مع دوال النقل
        migration_map = {
            'users': self.migrate_users,
            'employee_files': self.migrate_employee_files,
            'advance_files': self.migrate_advance_files,
            'statement_files': self.migrate_statement_files,
            'violation_files': self.migrate_violation_files,
            'termination_files': self.migrate_termination_files,
            'medical_insurance': self.migrate_medical_insurance,
            'medical_excuses': self.migrate_medical_excuses,
            'salary_adjustments': self.migrate_salary_adjustments,
            'employee_transfer_requests': self.migrate_transfer_requests,
            'attendance_records': self.migrate_attendance_records,
            'system_messages': self.migrate_system_messages,
            'notifications': self.migrate_notifications,
            'activity_logs': self.migrate_activity_logs,
        }

        if table == 'all':
            for table_name, migrate_func in migration_map.items():
                self._run_migration(table_name, migrate_func)
        elif table in migration_map:
            self._run_migration(table, migration_map[table])
        else:
            raise CommandError(
                f'جدول غير معروف: {table}. '
                f'الجداول المتاحة: {", ".join(migration_map.keys())}'
            )

        self.stdout.write(self.style.SUCCESS('\n🎉 تمت عملية النقل بنجاح!'))

    def _run_migration(self, table_name, migrate_func):
        """تشغيل نقل جدول واحد مع معالجة الأخطاء"""
        self.stdout.write(f'\n{"="*50}')
        self.stdout.write(f'📦 نقل جدول: {table_name}')
        self.stdout.write(f'{"="*50}')
        try:
            count = migrate_func()
            self.stdout.write(
                self.style.SUCCESS(f'  ✅ تم نقل {count} سجل من {table_name}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'  ❌ خطأ في نقل {table_name}: {e}')
            )
            logger.exception(f'Error migrating {table_name}')

    def _fetch_all(self, query):
        """جلب جميع السجلات من قاعدة البيانات القديمة"""
        with connections['legacy'].cursor() as cursor:
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def _get_user_map(self):
        """بناء خريطة ربط معرفات المستخدمين القديمة بالجديدة"""
        user_map = {}
        for user in User.objects.all():
            # نستخدم username كمفتاح الربط
            user_map[user.username] = user
        return user_map

    def _resolve_user(self, old_id, id_map):
        """تحويل معرف المستخدم القديم إلى كائن User جديد"""
        if old_id is None:
            return None
        return id_map.get(old_id)

    # ==============================
    # نقل المستخدمين
    # ==============================
    @transaction.atomic
    def migrate_users(self):
        rows = self._fetch_all('SELECT * FROM users ORDER BY id')
        count = 0
        old_to_new_id = {}

        for row in rows:
            if User.objects.filter(username=row['username']).exists():
                user = User.objects.get(username=row['username'])
                old_to_new_id[row['id']] = user
                self.stdout.write(f"  ⏩ المستخدم موجود: {row['username']}")
                continue

            if not self.dry_run:
                user = User(
                    username=row['username'],
                    # نحافظ على كلمة المرور المشفرة أو نضع واحدة مؤقتة
                    password=make_password('changeme123'),
                    first_name=row.get('full_name', '').split(' ')[0] if row.get('full_name') else '',
                    last_name=' '.join(row.get('full_name', '').split(' ')[1:]) if row.get('full_name') else '',
                    email=row.get('email', '') or '',
                    phone=row.get('phone'),
                    department=row.get('department'),
                    branch=row.get('branch'),
                    role=row.get('role', 'employee'),
                    is_active=bool(row.get('is_active', 1)),
                    is_staff=True,  # للوصول إلى لوحة الإدارة
                )
                # المدير يحصل على صلاحيات كاملة
                if row.get('role') == 'admin':
                    user.is_superuser = True
                user.save()
                old_to_new_id[row['id']] = user
            count += 1
            self.stdout.write(f"  ✓ {row['username']} ({row.get('role', 'employee')})")

        # حفظ الخريطة للاستخدام لاحقاً
        self._user_id_map = old_to_new_id
        return count

    # ==============================
    # نقل ملفات الموظفين
    # ==============================
    @transaction.atomic
    def migrate_employee_files(self):
        rows = self._fetch_all('SELECT * FROM employee_files ORDER BY id')
        if not hasattr(self, '_user_id_map'):
            self._build_user_id_map()

        objects = []
        for row in rows:
            obj = EmployeeFile(
                employee_name=row['employee_name'],
                employee_number=row.get('employee_number'),
                start_type=row.get('start_type', 'new'),
                national_id=row.get('national_id'),
                nationality=row.get('nationality'),
                start_date=row.get('start_date'),
                salary=row.get('salary'),
                branch=row.get('branch'),
                department=row.get('department'),
                cost_center=row.get('cost_center'),
                file_name=row.get('file_name'),
                notes=row.get('notes'),
                status=row.get('status', 'pending'),
                branch_manager_approval=row.get('branch_manager_approval', 'pending'),
                department_manager_approval=row.get('department_manager_approval', 'pending'),
                manager_approval=row.get('manager_approval', 'pending'),
                approval_notes=row.get('approval_notes'),
                assign_note=row.get('assign_note'),
                department_filter=row.get('department_filter'),
                assigned_employee_number=row.get('assigned_employee_number'),
                uploaded_by=self._resolve_user(row.get('uploaded_by'), self._user_id_map),
                assigned_to=self._resolve_user(row.get('assigned_to'), self._user_id_map),
                completed_by=self._resolve_user(row.get('completed_by'), self._user_id_map),
                branch_approved_by=self._resolve_user(row.get('branch_approved_by'), self._user_id_map),
                department_approved_by=self._resolve_user(row.get('department_approved_by'), self._user_id_map),
                manager_approved_by=self._resolve_user(row.get('manager_approved_by'), self._user_id_map),
            )
            if row.get('in_progress_at'):
                obj.in_progress_at = row['in_progress_at']
            if row.get('completed_at'):
                obj.completed_at = row['completed_at']
            objects.append(obj)

        if not self.dry_run:
            EmployeeFile.objects.bulk_create(objects, batch_size=self.batch_size)
        return len(objects)

    # ==============================
    # نقل ملفات السلف
    # ==============================
    @transaction.atomic
    def migrate_advance_files(self):
        rows = self._fetch_all('SELECT * FROM advance_files ORDER BY id')
        if not hasattr(self, '_user_id_map'):
            self._build_user_id_map()

        objects = []
        for row in rows:
            obj = AdvanceFile(
                employee_name=row['employee_name'],
                employee_number=row.get('employee_number'),
                advance_amount=row['advance_amount'],
                advance_date=row.get('advance_date'),
                branch=row.get('branch'),
                file_name=row.get('file_name'),
                notes=row.get('notes'),
                status=row.get('status', 'pending'),
                branch_manager_approval=row.get('branch_manager_approval', 'pending'),
                department_manager_approval=row.get('department_manager_approval', 'pending'),
                manager_approval=row.get('manager_approval', 'pending'),
                approval_notes=row.get('approval_notes'),
                assign_note=row.get('assign_note'),
                department_filter=row.get('department_filter'),
                uploaded_by=self._resolve_user(row.get('uploaded_by'), self._user_id_map),
                assigned_to=self._resolve_user(row.get('assigned_to'), self._user_id_map),
                completed_by=self._resolve_user(row.get('completed_by'), self._user_id_map),
                branch_approved_by=self._resolve_user(row.get('branch_approved_by'), self._user_id_map),
                department_approved_by=self._resolve_user(row.get('department_approved_by'), self._user_id_map),
                manager_approved_by=self._resolve_user(row.get('manager_approved_by'), self._user_id_map),
            )
            objects.append(obj)

        if not self.dry_run:
            AdvanceFile.objects.bulk_create(objects, batch_size=self.batch_size)
        return len(objects)

    # ==============================
    # نقل الإفادات والإجازات
    # ==============================
    @transaction.atomic
    def migrate_statement_files(self):
        rows = self._fetch_all('SELECT * FROM statement_files ORDER BY id')
        if not hasattr(self, '_user_id_map'):
            self._build_user_id_map()

        objects = []
        for row in rows:
            obj = StatementFile(
                employee_name=row['employee_name'],
                employee_number=row.get('employee_number'),
                statement_type=row['statement_type'],
                branch=row.get('branch'),
                vacation_days=row.get('vacation_days'),
                vacation_start=row.get('vacation_start'),
                vacation_end=row.get('vacation_end'),
                vacation_balance=row.get('vacation_balance'),
                file_name=row.get('file_name'),
                notes=row.get('notes'),
                status=row.get('status', 'pending'),
                branch_manager_approval=row.get('branch_manager_approval', 'pending'),
                department_manager_approval=row.get('department_manager_approval', 'pending'),
                manager_approval=row.get('manager_approval', 'pending'),
                approval_notes=row.get('approval_notes'),
                assign_note=row.get('assign_note'),
                department_filter=row.get('department_filter'),
                uploaded_by=self._resolve_user(row.get('uploaded_by'), self._user_id_map),
                assigned_to=self._resolve_user(row.get('assigned_to'), self._user_id_map),
                completed_by=self._resolve_user(row.get('completed_by'), self._user_id_map),
                branch_approved_by=self._resolve_user(row.get('branch_approved_by'), self._user_id_map),
                department_approved_by=self._resolve_user(row.get('department_approved_by'), self._user_id_map),
                manager_approved_by=self._resolve_user(row.get('manager_approved_by'), self._user_id_map),
            )
            objects.append(obj)

        if not self.dry_run:
            StatementFile.objects.bulk_create(objects, batch_size=self.batch_size)
        return len(objects)

    # ==============================
    # نقل المخالفات
    # ==============================
    @transaction.atomic
    def migrate_violation_files(self):
        rows = self._fetch_all('SELECT * FROM violation_files ORDER BY id')
        if not hasattr(self, '_user_id_map'):
            self._build_user_id_map()

        objects = []
        for row in rows:
            obj = ViolationFile(
                violation_type=row['violation_type'],
                employee_name=row['employee_name'],
                employee_number=row.get('employee_number'),
                violation_date=row.get('violation_date'),
                branch=row.get('branch'),
                employee_branch=row.get('employee_branch'),
                employee_department=row.get('employee_department'),
                violation_notes=row.get('violation_notes'),
                employee_statement=row.get('employee_statement'),
                status=row.get('status', 'pending'),
                branch_manager_approval=row.get('branch_manager_approval', 'pending'),
                department_manager_approval=row.get('department_manager_approval', 'pending'),
                manager_approval=row.get('manager_approval', 'pending'),
                approval_notes=row.get('approval_notes'),
                department_filter=row.get('department_filter'),
                uploaded_by=self._resolve_user(row.get('uploaded_by'), self._user_id_map),
                assigned_to=self._resolve_user(row.get('assigned_to'), self._user_id_map),
                branch_approved_by=self._resolve_user(row.get('branch_approved_by'), self._user_id_map),
                department_approved_by=self._resolve_user(row.get('department_approved_by'), self._user_id_map),
                manager_approved_by=self._resolve_user(row.get('manager_approved_by'), self._user_id_map),
            )
            objects.append(obj)

        if not self.dry_run:
            ViolationFile.objects.bulk_create(objects, batch_size=self.batch_size)
        return len(objects)

    # ==============================
    # نقل إنهاءات الخدمات
    # ==============================
    @transaction.atomic
    def migrate_termination_files(self):
        rows = self._fetch_all('SELECT * FROM termination_files ORDER BY id')
        if not hasattr(self, '_user_id_map'):
            self._build_user_id_map()

        objects = []
        for row in rows:
            obj = TerminationFile(
                employee_name=row['employee_name'],
                employee_number=row.get('employee_number'),
                national_id=row.get('national_id'),
                nationality=row.get('nationality'),
                branch=row.get('branch'),
                status=row.get('status', 'pending'),
                branch_manager_approval=row.get('branch_manager_approval', 'pending'),
                department_manager_approval=row.get('department_manager_approval', 'pending'),
                manager_approval=row.get('manager_approval', 'pending'),
                approval_notes=row.get('approval_notes'),
                department_filter=row.get('department_filter'),
                uploaded_by=self._resolve_user(row.get('uploaded_by'), self._user_id_map),
                assigned_to=self._resolve_user(row.get('assigned_to'), self._user_id_map),
                branch_approved_by=self._resolve_user(row.get('branch_approved_by'), self._user_id_map),
                department_approved_by=self._resolve_user(row.get('department_approved_by'), self._user_id_map),
                manager_approved_by=self._resolve_user(row.get('manager_approved_by'), self._user_id_map),
            )
            objects.append(obj)

        if not self.dry_run:
            TerminationFile.objects.bulk_create(objects, batch_size=self.batch_size)
        return len(objects)

    # ==============================
    # نقل التأمين الطبي
    # ==============================
    @transaction.atomic
    def migrate_medical_insurance(self):
        rows = self._fetch_all('SELECT * FROM medical_insurance ORDER BY id')
        if not hasattr(self, '_user_id_map'):
            self._build_user_id_map()

        objects = []
        for row in rows:
            obj = MedicalInsurance(
                insurance_type=row['insurance_type'],
                employee_name=row['employee_name'],
                details=row['details'],
                branch=row.get('branch'),
                status=row.get('status', 'pending'),
                branch_manager_approval=row.get('branch_manager_approval', 'pending'),
                department_manager_approval=row.get('department_manager_approval', 'pending'),
                manager_approval=row.get('manager_approval', 'pending'),
                approval_notes=row.get('approval_notes'),
                uploaded_by=self._resolve_user(row.get('uploaded_by'), self._user_id_map),
                assigned_to=self._resolve_user(row.get('assigned_to'), self._user_id_map),
                branch_approved_by=self._resolve_user(row.get('branch_approved_by'), self._user_id_map),
                department_approved_by=self._resolve_user(row.get('department_approved_by'), self._user_id_map),
                manager_approved_by=self._resolve_user(row.get('manager_approved_by'), self._user_id_map),
            )
            objects.append(obj)

        if not self.dry_run:
            MedicalInsurance.objects.bulk_create(objects, batch_size=self.batch_size)
        return len(objects)

    # ==============================
    # نقل الأعذار الطبية
    # ==============================
    @transaction.atomic
    def migrate_medical_excuses(self):
        rows = self._fetch_all('SELECT * FROM medical_excuses ORDER BY id')
        if not hasattr(self, '_user_id_map'):
            self._build_user_id_map()

        objects = []
        for row in rows:
            obj = MedicalExcuse(
                employee_name=row['employee_name'],
                employee_id_number=row['employee_id'],
                branch=row['branch'],
                department=row['department'],
                cost_center=row.get('cost_center'),
                excuse_reason=row['excuse_reason'],
                excuse_date=row.get('excuse_date'),
                excuse_duration=row.get('excuse_duration', 1),
                status=row.get('status', 'pending'),
                branch_manager_approval=row.get('branch_manager_approval', 'pending'),
                department_manager_approval=row.get('department_manager_approval', 'pending'),
                manager_approval=row.get('manager_approval', 'pending'),
                approval_notes=row.get('approval_notes'),
                department_filter=row.get('department_filter'),
                uploaded_by=self._resolve_user(row.get('uploaded_by'), self._user_id_map),
                assigned_to=self._resolve_user(row.get('assigned_to'), self._user_id_map),
                branch_approved_by=self._resolve_user(row.get('branch_approved_by'), self._user_id_map),
                department_approved_by=self._resolve_user(row.get('department_approved_by'), self._user_id_map),
                manager_approved_by=self._resolve_user(row.get('manager_approved_by'), self._user_id_map),
            )
            objects.append(obj)

        if not self.dry_run:
            MedicalExcuse.objects.bulk_create(objects, batch_size=self.batch_size)
        return len(objects)

    # ==============================
    # نقل تعديلات الرواتب
    # ==============================
    @transaction.atomic
    def migrate_salary_adjustments(self):
        rows = self._fetch_all('SELECT * FROM salary_adjustments ORDER BY id')
        if not hasattr(self, '_user_id_map'):
            self._build_user_id_map()

        objects = []
        for row in rows:
            obj = SalaryAdjustment(
                employee_number=row['employee_number'],
                employee_name=row['employee_name'],
                branch=row.get('branch'),
                department=row.get('department'),
                cost_center=row.get('cost_center'),
                current_salary=row.get('current_salary', 0),
                salary_increase=row.get('salary_increase', 0),
                new_salary=row.get('new_salary', 0),
                adjustment_reason=row.get('adjustment_reason'),
                notes=row.get('notes'),
                status=row.get('status', 'pending'),
                branch_manager_approval=row.get('branch_manager_approval', 'pending'),
                department_manager_approval=row.get('department_manager_approval', 'pending'),
                manager_approval=row.get('manager_approval', 'pending'),
                approval_notes=row.get('approval_notes'),
                uploaded_by=self._resolve_user(row.get('uploaded_by'), self._user_id_map),
                assigned_to=self._resolve_user(row.get('assigned_to'), self._user_id_map),
                branch_approved_by=self._resolve_user(row.get('branch_approved_by'), self._user_id_map),
                department_approved_by=self._resolve_user(row.get('department_approved_by'), self._user_id_map),
                manager_approved_by=self._resolve_user(row.get('manager_approved_by'), self._user_id_map),
            )
            objects.append(obj)

        if not self.dry_run:
            SalaryAdjustment.objects.bulk_create(objects, batch_size=self.batch_size)
        return len(objects)

    # ==============================
    # نقل طلبات النقل
    # ==============================
    @transaction.atomic
    def migrate_transfer_requests(self):
        rows = self._fetch_all('SELECT * FROM employee_transfer_requests ORDER BY id')
        if not hasattr(self, '_user_id_map'):
            self._build_user_id_map()

        objects = []
        for row in rows:
            obj = EmployeeTransferRequest(
                employee_name=row['employee_name'],
                employee_id_number=row['employee_id'],
                current_branch=row['current_branch'],
                requested_branch=row['requested_branch'],
                current_department=row['current_department'],
                requested_department=row['requested_department'],
                current_cost_center=row.get('current_cost_center'),
                new_cost_center=row.get('new_cost_center'),
                transfer_reason=row['transfer_reason'],
                preferred_date=row.get('preferred_date'),
                status=row.get('status', 'pending'),
                branch_manager_approval=row.get('branch_manager_approval', 'pending'),
                department_manager_approval=row.get('department_manager_approval', 'pending'),
                manager_approval=row.get('manager_approval', 'pending'),
                approval_notes=row.get('approval_notes'),
                assign_note=row.get('assign_note'),
                department_filter=row.get('department_filter'),
                uploaded_by=self._resolve_user(row.get('uploaded_by'), self._user_id_map),
                assigned_to=self._resolve_user(row.get('assigned_to'), self._user_id_map),
                completed_by=self._resolve_user(row.get('completed_by'), self._user_id_map),
                branch_approved_by=self._resolve_user(row.get('branch_approved_by'), self._user_id_map),
                department_approved_by=self._resolve_user(row.get('department_approved_by'), self._user_id_map),
                manager_approved_by=self._resolve_user(row.get('manager_approved_by'), self._user_id_map),
            )
            objects.append(obj)

        if not self.dry_run:
            EmployeeTransferRequest.objects.bulk_create(objects, batch_size=self.batch_size)
        return len(objects)

    # ==============================
    # نقل سجلات الحضور
    # ==============================
    @transaction.atomic
    def migrate_attendance_records(self):
        rows = self._fetch_all('SELECT * FROM attendance_records ORDER BY id')
        if not hasattr(self, '_user_id_map'):
            self._build_user_id_map()

        objects = []
        for row in rows:
            uploaded_by = self._resolve_user(row.get('uploaded_by'), self._user_id_map)
            if not uploaded_by:
                # إذا لم يُعثر على المستخدم، نستخدم أول مدير
                uploaded_by = User.objects.filter(is_superuser=True).first()
                if not uploaded_by:
                    continue

            obj = AttendanceRecord(
                batch_id=row.get('batch_id'),
                batch_date=row.get('batch_date'),
                employee_name=row.get('employee_name', ''),
                title=row.get('title'),
                branch=row.get('branch'),
                date_from=row.get('date_from'),
                attendance_date=row.get('attendance_date'),
                shift_start=row.get('shift_start'),
                shift_end=row.get('shift_end'),
                nationality=row.get('nationality'),
                notes=row.get('notes'),
                status=row.get('status', 'pending'),
                branch_manager_approval=row.get('branch_manager_approval', 'pending'),
                department_manager_approval=row.get('department_manager_approval', 'pending'),
                manager_approval=row.get('manager_approval', 'pending'),
                approval_notes=row.get('approval_notes'),
                assigned_to=self._resolve_user(row.get('assigned_to'), self._user_id_map),
                uploaded_by=uploaded_by,
            )
            objects.append(obj)

        if not self.dry_run:
            AttendanceRecord.objects.bulk_create(objects, batch_size=self.batch_size)
        return len(objects)

    # ==============================
    # نقل رسائل النظام
    # ==============================
    @transaction.atomic
    def migrate_system_messages(self):
        rows = self._fetch_all('SELECT * FROM system_messages ORDER BY id')
        if not hasattr(self, '_user_id_map'):
            self._build_user_id_map()

        objects = []
        for row in rows:
            created_by = self._resolve_user(row.get('created_by'), self._user_id_map)
            if not created_by:
                created_by = User.objects.filter(is_superuser=True).first()
                if not created_by:
                    continue

            obj = SystemMessage(
                title=row['title'],
                content=row['content'],
                message_type=row.get('message_type', 'info'),
                is_active=bool(row.get('is_active', 1)),
                created_by=created_by,
            )
            objects.append(obj)

        if not self.dry_run:
            SystemMessage.objects.bulk_create(objects, batch_size=self.batch_size)
        return len(objects)

    # ==============================
    # نقل الإشعارات
    # ==============================
    @transaction.atomic
    def migrate_notifications(self):
        rows = self._fetch_all('SELECT * FROM notifications ORDER BY id')
        if not hasattr(self, '_user_id_map'):
            self._build_user_id_map()

        objects = []
        for row in rows:
            user = self._resolve_user(row.get('user_id'), self._user_id_map)
            if not user:
                continue

            obj = Notification(
                user=user,
                title=row.get('title', ''),
                message=row.get('message', ''),
                notification_type=row.get('type', 'info'),
                link=row.get('link'),
                icon=row.get('icon'),
                is_read=bool(row.get('is_read', 0)),
                read_at=row.get('read_at'),
            )
            objects.append(obj)

        if not self.dry_run:
            Notification.objects.bulk_create(objects, batch_size=self.batch_size)
        return len(objects)

    # ==============================
    # نقل سجل النشاطات
    # ==============================
    @transaction.atomic
    def migrate_activity_logs(self):
        rows = self._fetch_all('SELECT * FROM activity_logs ORDER BY id')
        if not hasattr(self, '_user_id_map'):
            self._build_user_id_map()

        objects = []
        for row in rows:
            import json
            old_data = row.get('old_data')
            new_data = row.get('new_data')

            # تحويل البيانات من نص إلى JSON إذا لزم الأمر
            if isinstance(old_data, str):
                try:
                    old_data = json.loads(old_data)
                except (json.JSONDecodeError, TypeError):
                    old_data = None
            if isinstance(new_data, str):
                try:
                    new_data = json.loads(new_data)
                except (json.JSONDecodeError, TypeError):
                    new_data = None

            obj = ActivityLog(
                user=self._resolve_user(row.get('user_id'), self._user_id_map),
                username=row.get('username', ''),
                action=row.get('action', 'view'),
                module=row.get('module', ''),
                description=row.get('description'),
                target_id=row.get('target_id'),
                old_data=old_data,
                new_data=new_data,
                ip_address=row.get('ip_address'),
                user_agent=row.get('user_agent'),
                request_url=row.get('request_url'),
                request_method=row.get('request_method'),
            )
            objects.append(obj)

        if not self.dry_run:
            ActivityLog.objects.bulk_create(objects, batch_size=self.batch_size)
        return len(objects)

    # ==============================
    # أداة مساعدة لبناء خريطة المستخدمين
    # ==============================
    def _build_user_id_map(self):
        """بناء خريطة ربط معرف المستخدم القديم بكائن المستخدم الجديد"""
        self._user_id_map = {}
        try:
            old_users = self._fetch_all('SELECT id, username FROM users ORDER BY id')
            for old_user in old_users:
                try:
                    new_user = User.objects.get(username=old_user['username'])
                    self._user_id_map[old_user['id']] = new_user
                except User.DoesNotExist:
                    pass
        except Exception:
            pass
