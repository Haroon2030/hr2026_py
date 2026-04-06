"""
استيراد تزايدي للبيانات من ملف SQL القديم (MySQL/PHP) إلى Django
================================================================
الاستخدام:
    python manage.py import_from_sql                        # استيراد الجديد فقط
    python manage.py import_from_sql --update               # استيراد + تحديث الموجود
    python manage.py import_from_sql --clean                # مسح ثم استيراد
    python manage.py import_from_sql --file /path/to/file.sql
    python manage.py import_from_sql --sync-files           # رفع الملفات الجديدة إلى R2
"""
import os
import re
import sys
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone as dt_timezone
from typing import Any, Dict, List, Optional
from pathlib import Path

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.core.models import (
    EmployeeFile, AdvanceFile, StatementFile, ViolationFile,
    TerminationFile, MedicalInsurance, MedicalExcuse,
    SalaryAdjustment, EmployeeTransferRequest, AttendanceRecord,
    RequestStatus, ApprovalStatus, StartType,
    Branch, CostCenter, Organization, Sponsorship,
    UserMessage,
)

User = get_user_model()


class Command(BaseCommand):
    help = 'استيراد تزايدي: يستورد السجلات الجديدة فقط من SQL القديم بدون تكرار'

    def add_arguments(self, parser):
        parser.add_argument('--clean', action='store_true', help='مسح البيانات القديمة أولاً')
        parser.add_argument('--update', action='store_true', help='تحديث السجلات الموجودة إذا تغيّرت')
        parser.add_argument('--file', type=str, help='مسار ملف SQL', default=None)
        parser.add_argument('--sync-files', action='store_true', help='رفع الملفات الجديدة إلى R2 بعد الاستيراد')

    def handle(self, *args, **options):
        self.admin_user: Any = User.objects.filter(is_superuser=True).first() or User.objects.first()
        if not self.admin_user:
            self.stderr.write("لا يوجد مستخدمين!")
            return

        self.branch_cache: Dict[str, Branch] = {}
        self.cost_center_cache: Dict[str, CostCenter] = {}
        self.user_cache: Dict[int, Any] = {}
        self.update_mode = options.get('update', False)
        self._reset_stats()
        # إحصائيات إجمالية
        self.total_stats = {'imported': 0, 'updated': 0, 'skipped': 0, 'errors': 0}

        # البحث عن ملف SQL
        sql_file = options.get('file')
        if not sql_file:
            candidates = [
                Path('/app/data/u824688047_hr_pro.sql'),
                Path('/app/u824688047_hr_pro.sql'),
                Path(__file__).resolve().parent.parent.parent.parent.parent / 'data' / 'u824688047_hr_pro.sql',
                Path(__file__).resolve().parent.parent.parent.parent.parent.parent / 'u824688047_hr_pro.sql',
            ]
            for c in candidates:
                if c.exists():
                    sql_file = str(c)
                    break

        if not sql_file or not Path(sql_file).exists():
            self.stderr.write("ملف SQL غير موجود! جرب: --file /path/to/file.sql")
            return

        self.stdout.write("=" * 60)
        self.stdout.write("         استيراد تزايدي لبيانات HR Pro")
        self.stdout.write("=" * 60)
        self.stdout.write(f"المستخدم: {self.admin_user}")
        self.stdout.write(f"الملف: {sql_file}")
        mode = "استيراد + تحديث" if self.update_mode else "استيراد الجديد فقط (بدون تكرار)"
        self.stdout.write(f"الوضع: {mode}")

        if options['clean']:
            self._clean_data()

        with open(sql_file, 'r', encoding='utf-8') as f:
            content = f.read()
        self.stdout.write(f"حجم الملف: {len(content):,} حرف")

        self._import_branches(content)
        self._import_cost_centers(content)
        self._import_organizations(content)
        self._import_sponsorships(content)
        self._import_employees(content)
        self._import_advances(content)
        self._import_statements(content)
        self._import_violations(content)
        self._import_terminations(content)
        self._import_medical_insurance(content)
        self._import_medical_excuses(content)
        self._import_salary_adjustments(content)
        self._import_transfers(content)
        self._import_attendance(content)
        self._import_messages(content)

        self._print_summary()

        if options.get('sync_files'):
            self._sync_files_to_r2()

    # ==============================
    # SQL Parsing
    # ==============================
    def _parse_sql_value(self, v):
        v = v.strip()
        if v.upper() == 'NULL':
            return None
        if v.startswith("'") and v.endswith("'"):
            inner = v[1:-1]
            return inner.replace("\\'", "'").replace('\\\\', '\\').replace('\\n', '\n').replace('\\r', '\r')
        try:
            return Decimal(v) if '.' in v else int(v)
        except (ValueError, InvalidOperation):
            return v

    def _parse_row_values(self, row_str):
        values, current, in_quote = [], "", False
        for i, char in enumerate(row_str):
            if char == "'" and (i == 0 or row_str[i-1] != '\\'):
                in_quote = not in_quote
                current += char
            elif char == ',' and not in_quote:
                values.append(self._parse_sql_value(current.strip()))
                current = ""
            else:
                current += char
        if current.strip():
            values.append(self._parse_sql_value(current.strip()))
        return values

    def _extract_rows(self, content, table_name):
        pattern = rf"INSERT INTO `{table_name}`[^V]*VALUES\s*"
        rows = []
        for match in re.finditer(pattern, content):
            i = match.end()
            while i < len(content):
                if content[i] == '(':
                    depth, in_quote, j = 1, False, i + 1
                    while j < len(content) and depth > 0:
                        c = content[j]
                        if c == "'" and (j == 0 or content[j-1] != '\\'):
                            in_quote = not in_quote
                        elif not in_quote:
                            depth += 1 if c == '(' else (-1 if c == ')' else 0)
                        j += 1
                    rows.append(content[i+1:j-1])
                    i = j
                elif content[i] == ';':
                    break
                else:
                    i += 1
        return rows

    def _extract_columns(self, content, table_name):
        pattern = rf"INSERT INTO `{table_name}`\s*\(([^)]+)\)\s*VALUES"
        match = re.search(pattern, content)
        if not match:
            return []
        return re.findall(r'`([^`]+)`', match.group(1))

    # ==============================
    # Helpers
    # ==============================
    def _reset_stats(self):
        self.stats = {'imported': 0, 'updated': 0, 'skipped': 0, 'errors': 0}

    def _accumulate_stats(self):
        for k in self.total_stats:
            self.total_stats[k] += self.stats[k]

    def _print_stats(self, label):
        parts = [f"NEW {self.stats['imported']}"]
        if self.update_mode:
            parts.append(f"UPD {self.stats['updated']}")
        parts.extend([f"SKIP {self.stats['skipped']}", f"ERR {self.stats['errors']}"])
        self.stdout.write(f"   {' | '.join(parts)}")
        self._accumulate_stats()

    def _save_record(self, model_class, record_id, defaults, ts_field='created_at', ts_value=None):
        existing = model_class.objects.filter(pk=record_id).first()
        if existing:
            if self.update_mode:
                changed = False
                for key, value in defaults.items():
                    old_val = getattr(existing, key, None)
                    if old_val != value:
                        setattr(existing, key, value)
                        changed = True
                if changed:
                    existing.save()
                    if ts_field and ts_value:
                        model_class.objects.filter(pk=record_id).update(**{ts_field: ts_value})
                    return 'updated'
                return 'skipped'
            return 'skipped'
        else:
            obj = model_class(id=record_id, **defaults)
            obj.save()
            if ts_field and ts_value:
                model_class.objects.filter(pk=record_id).update(**{ts_field: ts_value})
            return 'imported'

    def _parse_datetime(self, val):
        if not val or not isinstance(val, str):
            return None
        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d']:
            try:
                return datetime.strptime(val.strip(), fmt).replace(tzinfo=dt_timezone.utc)
            except ValueError:
                continue
        return None

    def _parse_date(self, val):
        if not val or not isinstance(val, str):
            return None
        try:
            return datetime.strptime(val.strip(), '%Y-%m-%d').date()
        except ValueError:
            return None

    def _get_user(self, user_id):
        if not user_id:
            return None
        try:
            uid = int(user_id)
            if uid not in self.user_cache:
                try:
                    self.user_cache[uid] = User.objects.get(pk=uid)
                except User.DoesNotExist:
                    self.user_cache[uid] = None
            return self.user_cache[uid]
        except (ValueError, TypeError):
            return None

    def _get_user_id(self, val):
        user = self._get_user(val)
        return user.id if user else None

    def _to_decimal(self, v):
        try:
            return Decimal(str(v or 0))
        except (InvalidOperation, ValueError):
            return Decimal('0')

    def _to_int(self, v):
        try:
            return int(v) if v else 0
        except (ValueError, TypeError):
            return 0

    def _clean_status(self, val, choices_class):
        if not val:
            return None
        val = str(val).strip().lower()
        valid = [c[0] for c in choices_class.choices]
        return val if val in valid else None

    def _get_or_create_branch(self, name):
        if not name:
            return None
        name = str(name).strip()
        if not name:
            return None
        if name not in self.branch_cache:
            branch, _ = Branch.objects.get_or_create(name=name)
            self.branch_cache[name] = branch
        return self.branch_cache[name]

    def _get_or_create_cost_center(self, name):
        if not name:
            return None
        name = str(name).strip()
        if not name:
            return None
        if name not in self.cost_center_cache:
            cc, _ = CostCenter.objects.get_or_create(name=name)
            self.cost_center_cache[name] = cc
        return self.cost_center_cache[name]

    # ==============================
    # Clean
    # ==============================
    def _clean_data(self):
        self.stdout.write("\nمسح البيانات القديمة...")
        for model, name in [
            (UserMessage, 'الرسائل'), (AttendanceRecord, 'الحضور'),
            (EmployeeTransferRequest, 'النقل'), (SalaryAdjustment, 'تعديلات الرواتب'),
            (MedicalExcuse, 'الأعذار الطبية'), (MedicalInsurance, 'التأمين'),
            (TerminationFile, 'إنهاء الخدمات'), (ViolationFile, 'المخالفات'),
            (StatementFile, 'البيانات'), (AdvanceFile, 'السلف'),
            (EmployeeFile, 'الموظفين'), (Branch, 'الفروع'),
            (CostCenter, 'مراكز التكلفة'), (Organization, 'المؤسسات'),
            (Sponsorship, 'الكفالات'),
        ]:
            count = model.objects.count()
            model.objects.all().delete()
            self.stdout.write(f"   حذف {name}: {count}")
        self.stdout.write("   تم المسح!")

    # ==============================
    # Simple models
    # ==============================
    def _import_simple(self, content, table_name, model_class, label):
        self.stdout.write(f"\n{label}...")
        self._reset_stats()
        for row_str in self._extract_rows(content, table_name):
            values = self._parse_row_values(row_str)
            if len(values) >= 2:
                record_id, name = values[0], values[1]
                if name:
                    name = str(name).strip()
                    try:
                        result = self._save_record(model_class, record_id, {'name': name})
                        self.stats[result] += 1
                    except Exception:
                        self.stats['errors'] += 1
                else:
                    self.stats['skipped'] += 1
        self._print_stats(label)

    def _import_branches(self, content):
        self._import_simple(content, 'branches', Branch, 'استيراد الفروع')

    def _import_cost_centers(self, content):
        self._import_simple(content, 'cost_centers', CostCenter, 'استيراد مراكز التكلفة')

    def _import_organizations(self, content):
        self._import_simple(content, 'organizations', Organization, 'استيراد المؤسسات')

    def _import_sponsorships(self, content):
        self._import_simple(content, 'sponsorships', Sponsorship, 'استيراد الكفالات')

    # ==============================
    # Employees
    # ==============================
    def _import_employees(self, content):
        self.stdout.write("\nاستيراد الموظفين...")
        self._reset_stats()
        cols = self._extract_columns(content, 'employee_files')
        if not cols:
            self.stdout.write("   لا توجد بيانات")
            return
        for row_str in self._extract_rows(content, 'employee_files'):
            try:
                values = self._parse_row_values(row_str)
                values += [None] * (len(cols) - len(values))
                data = dict(zip(cols, values))
                record_id = data['id']
                st = str(data.get('start_type') or '').lower()
                start_type = StartType.REPLACEMENT if st in ['transfer', 'نقل', 'replacement', 'بديل'] else StartType.NEW
                defaults = {
                    'employee_name': str(data['employee_name'] or ''),
                    'employee_number': str(data.get('employee_number') or '') or None,
                    'national_id': str(data.get('national_id') or '') or None,
                    'nationality': str(data.get('nationality') or '') or None,
                    'department': str(data.get('department') or '') or None,
                    'start_type': start_type,
                    'start_date': self._parse_date(data.get('start_date')),
                    'salary': self._to_decimal(data.get('salary')),
                    'branch': self._get_or_create_branch(data.get('branch')),
                    'department_filter': data.get('department_filter'),
                    'cost_center': self._get_or_create_cost_center(data.get('cost_center')),
                    'notes': data.get('notes'),
                    'file_path': data.get('file_path') or '',
                    'file_name': data.get('file_name') or data.get('original_filename'),
                    'status': self._clean_status(data.get('status'), RequestStatus) or RequestStatus.PENDING,
                    'branch_manager_approval': self._clean_status(data.get('branch_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    'department_manager_approval': self._clean_status(data.get('department_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    'manager_approval': self._clean_status(data.get('manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    'approval_notes': data.get('approval_notes'),
                    'uploaded_by_id': self._get_user_id(data.get('uploaded_by')) or self.admin_user.id,
                    'assigned_to_id': self._get_user_id(data.get('assigned_to')),
                    'completed_by_id': self._get_user_id(data.get('completed_by')),
                    'branch_approved_by_id': self._get_user_id(data.get('branch_approved_by')),
                    'department_approved_by_id': self._get_user_id(data.get('department_approved_by')),
                    'manager_approved_by_id': self._get_user_id(data.get('manager_approved_by')),
                    'assigned_employee_number': data.get('assigned_employee_number'),
                }
                ts = self._parse_datetime(data.get('created_at'))
                result = self._save_record(EmployeeFile, record_id, defaults, 'created_at', ts)
                self.stats[result] += 1
            except Exception as e:
                self.stats['errors'] += 1
                if self.stats['errors'] <= 3:
                    self.stderr.write(f"   ERR ID {data.get('id')}: {e}")
        self._print_stats('الموظفين')

    # ==============================
    # Advances
    # ==============================
    def _import_advances(self, content):
        self.stdout.write("\nاستيراد السلف...")
        self._reset_stats()
        cols = self._extract_columns(content, 'advance_files')
        if not cols:
            self.stdout.write("   لا توجد بيانات")
            return
        for row_str in self._extract_rows(content, 'advance_files'):
            try:
                values = self._parse_row_values(row_str)
                values += [None] * (len(cols) - len(values))
                data = dict(zip(cols, values))
                record_id = data['id']
                defaults = {
                    'employee_name': str(data['employee_name'] or ''),
                    'employee_number': str(data.get('employee_number') or '') or None,
                    'advance_amount': self._to_decimal(data.get('advance_amount')),
                    'advance_date': self._parse_date(data.get('advance_date')),
                    'file_path': data.get('file_path') or '',
                    'file_name': data.get('file_name') or data.get('original_filename'),
                    'notes': data.get('notes'),
                    'status': self._clean_status(data.get('status'), RequestStatus) or RequestStatus.PENDING,
                    'branch': self._get_or_create_branch(data.get('branch')),
                    'department_filter': data.get('department_filter'),
                    'installments': self._to_int(data.get('installments')) or 1,
                    'branch_manager_approval': self._clean_status(data.get('branch_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    'department_manager_approval': self._clean_status(data.get('department_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    'manager_approval': self._clean_status(data.get('manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    'approval_notes': data.get('approval_notes'),
                    'uploaded_by_id': self._get_user_id(data.get('uploaded_by')) or self.admin_user.id,
                    'assigned_to_id': self._get_user_id(data.get('assigned_to')),
                    'completed_by_id': self._get_user_id(data.get('completed_by')),
                    'branch_approved_by_id': self._get_user_id(data.get('branch_approved_by')),
                    'department_approved_by_id': self._get_user_id(data.get('department_approved_by')),
                    'manager_approved_by_id': self._get_user_id(data.get('manager_approved_by')),
                }
                ts = self._parse_datetime(data.get('created_at'))
                result = self._save_record(AdvanceFile, record_id, defaults, 'created_at', ts)
                self.stats[result] += 1
            except Exception as e:
                self.stats['errors'] += 1
        self._print_stats('السلف')

    # ==============================
    # Statements
    # ==============================
    def _import_statements(self, content):
        self.stdout.write("\nاستيراد البيانات والإجازات...")
        self._reset_stats()
        cols = self._extract_columns(content, 'statement_files')
        if not cols:
            self.stdout.write("   لا توجد بيانات")
            return
        for row_str in self._extract_rows(content, 'statement_files'):
            try:
                values = self._parse_row_values(row_str)
                values += [None] * (len(cols) - len(values))
                data = dict(zip(cols, values))
                record_id = data['id']
                defaults = {
                    'employee_name': str(data['employee_name'] or ''),
                    'employee_number': str(data.get('employee_number') or '') or None,
                    'statement_type': str(data.get('statement_type') or ''),
                    'file_path': data.get('file_path') or '',
                    'file_name': data.get('file_name') or data.get('original_filename'),
                    'notes': data.get('notes'),
                    'status': self._clean_status(data.get('status'), RequestStatus) or RequestStatus.PENDING,
                    'branch': self._get_or_create_branch(data.get('branch')),
                    'department_filter': data.get('department_filter'),
                    'vacation_days': self._to_int(data.get('vacation_days')),
                    'vacation_start': self._parse_date(data.get('vacation_start')),
                    'vacation_end': self._parse_date(data.get('vacation_end')),
                    'vacation_balance': self._to_decimal(data.get('vacation_balance')),
                    'branch_manager_approval': self._clean_status(data.get('branch_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    'department_manager_approval': self._clean_status(data.get('department_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    'manager_approval': self._clean_status(data.get('manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    'approval_notes': data.get('approval_notes'),
                    'uploaded_by_id': self._get_user_id(data.get('uploaded_by')) or self.admin_user.id,
                    'assigned_to_id': self._get_user_id(data.get('assigned_to')),
                    'completed_by_id': self._get_user_id(data.get('completed_by')),
                    'branch_approved_by_id': self._get_user_id(data.get('branch_approved_by')),
                    'department_approved_by_id': self._get_user_id(data.get('department_approved_by')),
                    'manager_approved_by_id': self._get_user_id(data.get('manager_approved_by')),
                }
                ts = self._parse_datetime(data.get('created_at'))
                result = self._save_record(StatementFile, record_id, defaults, 'created_at', ts)
                self.stats[result] += 1
            except Exception as e:
                self.stats['errors'] += 1
                if self.stats['errors'] == 1:
                    self.stderr.write(f"   ERR: {e}")
        self._print_stats('البيانات/الإجازات')

    # ==============================
    # Violations
    # ==============================
    def _import_violations(self, content):
        self.stdout.write("\nاستيراد المخالفات...")
        self._reset_stats()
        cols = self._extract_columns(content, 'violation_files')
        if not cols:
            self.stdout.write("   لا توجد بيانات")
            return
        for row_str in self._extract_rows(content, 'violation_files'):
            try:
                values = self._parse_row_values(row_str)
                values += [None] * (len(cols) - len(values))
                data = dict(zip(cols, values))
                record_id = data['id']
                defaults = {
                    'employee_name': str(data['employee_name'] or ''),
                    'employee_number': str(data.get('employee_number') or '') or None,
                    'violation_type': str(data.get('violation_type') or ''),
                    'violation_date': self._parse_date(data.get('violation_date')),
                    'file_path': data.get('file_path') or '',
                    'violation_notes': data.get('violation_notes'),
                    'employee_statement': data.get('employee_statement'),
                    'status': self._clean_status(data.get('status'), RequestStatus) or RequestStatus.PENDING,
                    'branch': self._get_or_create_branch(data.get('branch')),
                    'employee_branch': self._get_or_create_branch(data.get('employee_branch')),
                    'employee_department': data.get('employee_department'),
                    'department_filter': data.get('department_filter'),
                    'branch_manager_approval': self._clean_status(data.get('branch_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    'department_manager_approval': self._clean_status(data.get('department_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    'manager_approval': self._clean_status(data.get('manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    'approval_notes': data.get('approval_notes'),
                    'uploaded_by_id': self._get_user_id(data.get('uploaded_by')) or self.admin_user.id,
                    'assigned_to_id': self._get_user_id(data.get('assigned_to')),
                    'branch_approved_by_id': self._get_user_id(data.get('branch_approved_by')),
                    'department_approved_by_id': self._get_user_id(data.get('department_approved_by')),
                    'manager_approved_by_id': self._get_user_id(data.get('manager_approved_by')),
                }
                ts = self._parse_datetime(data.get('uploaded_at'))
                result = self._save_record(ViolationFile, record_id, defaults, 'created_at', ts)
                self.stats[result] += 1
            except Exception as e:
                self.stats['errors'] += 1
                if self.stats['errors'] == 1:
                    self.stderr.write(f"   ERR: {e}")
        self._print_stats('المخالفات')

    # ==============================
    # Terminations
    # ==============================
    def _import_terminations(self, content):
        self.stdout.write("\nاستيراد إنهاء الخدمات...")
        self._reset_stats()
        cols = self._extract_columns(content, 'termination_files')
        if not cols:
            self.stdout.write("   لا توجد بيانات")
            return
        for row_str in self._extract_rows(content, 'termination_files'):
            try:
                values = self._parse_row_values(row_str)
                values += [None] * (len(cols) - len(values))
                data = dict(zip(cols, values))
                record_id = data['id']
                defaults = {
                    'employee_name': str(data['employee_name'] or ''),
                    'employee_number': str(data.get('employee_number') or '') or None,
                    'national_id': str(data.get('national_id') or '') or None,
                    'nationality': str(data.get('nationality') or '') or None,
                    'notes': data.get('notes'),
                    'file_path': data.get('file_path') or '',
                    'status': self._clean_status(data.get('status'), RequestStatus) or RequestStatus.PENDING,
                    'branch': self._get_or_create_branch(data.get('branch')),
                    'department_filter': data.get('department_filter'),
                    'branch_manager_approval': self._clean_status(data.get('branch_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    'department_manager_approval': self._clean_status(data.get('department_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    'manager_approval': self._clean_status(data.get('manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    'approval_notes': data.get('approval_notes'),
                    'uploaded_by_id': self._get_user_id(data.get('uploaded_by')) or self.admin_user.id,
                    'assigned_to_id': self._get_user_id(data.get('assigned_to')),
                    'branch_approved_by_id': self._get_user_id(data.get('branch_approved_by')),
                    'department_approved_by_id': self._get_user_id(data.get('department_approved_by')),
                    'manager_approved_by_id': self._get_user_id(data.get('manager_approved_by')),
                }
                ts = self._parse_datetime(data.get('created_at'))
                result = self._save_record(TerminationFile, record_id, defaults, 'created_at', ts)
                self.stats[result] += 1
            except Exception as e:
                self.stats['errors'] += 1
        self._print_stats('إنهاء الخدمات')

    # ==============================
    # Medical Insurance
    # ==============================
    def _import_medical_insurance(self, content):
        self.stdout.write("\nاستيراد التأمين الطبي...")
        self._reset_stats()
        cols = self._extract_columns(content, 'medical_insurance')
        if not cols:
            self.stdout.write("   لا توجد بيانات")
            return
        for row_str in self._extract_rows(content, 'medical_insurance'):
            try:
                values = self._parse_row_values(row_str)
                values += [None] * (len(cols) - len(values))
                data = dict(zip(cols, values))
                record_id = data['id']
                defaults = {
                    'employee_name': str(data['employee_name'] or ''),
                    'insurance_type': str(data.get('insurance_type') or ''),
                    'details': str(data.get('details') or ''),
                    'file_path': data.get('file_path') or '',
                    'status': self._clean_status(data.get('status'), RequestStatus) or RequestStatus.PENDING,
                    'branch': self._get_or_create_branch(data.get('branch')),
                    'department_filter': data.get('department_filter'),
                    'branch_manager_approval': self._clean_status(data.get('branch_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    'department_manager_approval': self._clean_status(data.get('department_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    'manager_approval': self._clean_status(data.get('manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    'approval_notes': data.get('approval_notes'),
                    'uploaded_by_id': self._get_user_id(data.get('uploaded_by')) or self.admin_user.id,
                    'assigned_to_id': self._get_user_id(data.get('assigned_to')),
                    'branch_approved_by_id': self._get_user_id(data.get('branch_approved_by')),
                    'department_approved_by_id': self._get_user_id(data.get('department_approved_by')),
                    'manager_approved_by_id': self._get_user_id(data.get('manager_approved_by')),
                }
                ts = self._parse_datetime(data.get('uploaded_at'))
                result = self._save_record(MedicalInsurance, record_id, defaults, 'created_at', ts)
                self.stats[result] += 1
            except Exception as e:
                self.stats['errors'] += 1
                if self.stats['errors'] == 1:
                    self.stderr.write(f"   ERR: {e}")
        self._print_stats('التأمين الطبي')

    # ==============================
    # Medical Excuses
    # ==============================
    def _import_medical_excuses(self, content):
        self.stdout.write("\nاستيراد الأعذار الطبية...")
        self._reset_stats()
        cols = self._extract_columns(content, 'medical_excuses')
        if not cols:
            self.stdout.write("   لا توجد بيانات")
            return
        for row_str in self._extract_rows(content, 'medical_excuses'):
            try:
                values = self._parse_row_values(row_str)
                values += [None] * (len(cols) - len(values))
                data = dict(zip(cols, values))
                record_id = data['id']
                defaults = {
                    'employee_name': str(data['employee_name'] or ''),
                    'employee_id_number': str(data.get('employee_id') or ''),
                    'branch': str(data.get('branch') or ''),
                    'department': str(data.get('department') or ''),
                    'cost_center': self._get_or_create_cost_center(data.get('cost_center')),
                    'excuse_reason': str(data.get('excuse_reason') or ''),
                    'excuse_date': self._parse_date(data.get('excuse_date')),
                    'excuse_duration': self._to_int(data.get('excuse_duration')) or 1,
                    'file_path': data.get('file_path') or '',
                    'status': self._clean_status(data.get('status'), RequestStatus) or RequestStatus.PENDING,
                    'department_filter': data.get('department_filter'),
                    'branch_manager_approval': self._clean_status(data.get('branch_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    'department_manager_approval': self._clean_status(data.get('department_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    'manager_approval': self._clean_status(data.get('manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    'approval_notes': data.get('approval_notes'),
                    'uploaded_by_id': self._get_user_id(data.get('uploaded_by')) or self.admin_user.id,
                    'assigned_to_id': self._get_user_id(data.get('assigned_to')),
                    'branch_approved_by_id': self._get_user_id(data.get('branch_approved_by')),
                    'department_approved_by_id': self._get_user_id(data.get('department_approved_by')),
                    'manager_approved_by_id': self._get_user_id(data.get('manager_approved_by')),
                }
                ts = self._parse_datetime(data.get('created_at'))
                result = self._save_record(MedicalExcuse, record_id, defaults, 'created_at', ts)
                self.stats[result] += 1
            except Exception as e:
                self.stats['errors'] += 1
                if self.stats['errors'] == 1:
                    self.stderr.write(f"   ERR: {e}")
        self._print_stats('الأعذار الطبية')

    # ==============================
    # Salary Adjustments
    # ==============================
    def _import_salary_adjustments(self, content):
        self.stdout.write("\nاستيراد تعديلات الرواتب...")
        self._reset_stats()
        cols = self._extract_columns(content, 'salary_adjustments')
        if not cols:
            self.stdout.write("   لا توجد بيانات")
            return
        for row_str in self._extract_rows(content, 'salary_adjustments'):
            try:
                values = self._parse_row_values(row_str)
                values += [None] * (len(cols) - len(values))
                data = dict(zip(cols, values))
                record_id = data['id']
                defaults = {
                    'employee_name': str(data['employee_name'] or ''),
                    'employee_number': str(data.get('employee_number') or ''),
                    'department': str(data.get('department') or ''),
                    'current_salary': self._to_decimal(data.get('current_salary')),
                    'salary_increase': self._to_decimal(data.get('salary_increase')),
                    'new_salary': self._to_decimal(data.get('new_salary')),
                    'adjustment_reason': data.get('adjustment_reason'),
                    'notes': data.get('notes'),
                    'status': self._clean_status(data.get('status'), RequestStatus) or RequestStatus.PENDING,
                    'branch': self._get_or_create_branch(data.get('branch')),
                    'cost_center': self._get_or_create_cost_center(data.get('cost_center')),
                    'department_filter': data.get('department_filter'),
                    'branch_manager_approval': self._clean_status(data.get('branch_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    'department_manager_approval': self._clean_status(data.get('department_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    'manager_approval': self._clean_status(data.get('manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    'approval_notes': data.get('approval_notes'),
                    'uploaded_by_id': self._get_user_id(data.get('uploaded_by')) or self.admin_user.id,
                    'assigned_to_id': self._get_user_id(data.get('assigned_to')),
                    'branch_approved_by_id': self._get_user_id(data.get('branch_approved_by')),
                    'department_approved_by_id': self._get_user_id(data.get('department_approved_by')),
                    'manager_approved_by_id': self._get_user_id(data.get('manager_approved_by')),
                }
                ts = self._parse_datetime(data.get('created_at'))
                result = self._save_record(SalaryAdjustment, record_id, defaults, 'created_at', ts)
                self.stats[result] += 1
            except Exception as e:
                self.stats['errors'] += 1
                if self.stats['errors'] == 1:
                    self.stderr.write(f"   ERR: {e}")
        self._print_stats('تعديلات الرواتب')

    # ==============================
    # Transfers
    # ==============================
    def _import_transfers(self, content):
        self.stdout.write("\nاستيراد طلبات النقل...")
        self._reset_stats()
        cols = self._extract_columns(content, 'employee_transfer_requests')
        if not cols:
            self.stdout.write("   لا توجد بيانات")
            return
        for row_str in self._extract_rows(content, 'employee_transfer_requests'):
            try:
                values = self._parse_row_values(row_str)
                values += [None] * (len(cols) - len(values))
                data = dict(zip(cols, values))
                record_id = data['id']
                defaults = {
                    'employee_name': str(data['employee_name'] or ''),
                    'employee_id_number': str(data.get('employee_id') or ''),
                    'current_branch': self._get_or_create_branch(data.get('current_branch')),
                    'requested_branch': self._get_or_create_branch(data.get('requested_branch')),
                    'current_department': str(data.get('current_department') or ''),
                    'requested_department': str(data.get('requested_department') or ''),
                    'department_filter': data.get('department_filter'),
                    'current_cost_center': self._get_or_create_cost_center(data.get('current_cost_center')),
                    'new_cost_center': self._get_or_create_cost_center(data.get('new_cost_center')),
                    'transfer_reason': str(data.get('transfer_reason') or ''),
                    'preferred_date': self._parse_date(data.get('preferred_date')),
                    'status': self._clean_status(data.get('status'), RequestStatus) or RequestStatus.PENDING,
                    'assign_note': data.get('assign_note'),
                    'in_progress_at': self._parse_datetime(data.get('in_progress_at')),
                    'completed_at': self._parse_datetime(data.get('completed_at')),
                    'branch_manager_approval': self._clean_status(data.get('branch_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    'department_manager_approval': self._clean_status(data.get('department_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    'manager_approval': self._clean_status(data.get('manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    'approval_notes': data.get('approval_notes'),
                    'uploaded_by_id': self._get_user_id(data.get('uploaded_by')) or self.admin_user.id,
                    'assigned_to_id': self._get_user_id(data.get('assigned_to')),
                    'completed_by_id': self._get_user_id(data.get('completed_by')),
                    'branch_approved_by_id': self._get_user_id(data.get('branch_approved_by')),
                    'department_approved_by_id': self._get_user_id(data.get('department_approved_by')),
                    'manager_approved_by_id': self._get_user_id(data.get('manager_approved_by')),
                }
                ts = self._parse_datetime(data.get('created_at'))
                result = self._save_record(EmployeeTransferRequest, record_id, defaults, 'created_at', ts)
                self.stats[result] += 1
            except Exception as e:
                self.stats['errors'] += 1
                if self.stats['errors'] == 1:
                    self.stderr.write(f"   ERR: {e}")
        self._print_stats('طلبات النقل')

    # ==============================
    # Attendance
    # ==============================
    def _import_attendance(self, content):
        self.stdout.write("\nاستيراد سجلات الحضور...")
        self._reset_stats()
        cols = self._extract_columns(content, 'attendance_records')
        if not cols:
            self.stdout.write("   لا توجد بيانات")
            return
        for row_str in self._extract_rows(content, 'attendance_records'):
            try:
                values = self._parse_row_values(row_str)
                values += [None] * (len(cols) - len(values))
                data = dict(zip(cols, values))
                record_id = data['id']
                defaults = {
                    'batch_id': str(data.get('batch_id') or ''),
                    'batch_date': self._parse_date(data.get('batch_date')),
                    'employee_name': str(data['employee_name'] or ''),
                    'title': data.get('title'),
                    'branch': self._get_or_create_branch(data.get('branch')),
                    'department_filter': data.get('department_filter'),
                    'date_from': self._parse_date(data.get('date_from')),
                    'nationality': data.get('nationality'),
                    'shift_start': data.get('shift_start'),
                    'shift_end': data.get('shift_end'),
                    'attendance_date': self._parse_date(data.get('attendance_date')),
                    'notes': data.get('notes'),
                    'status': self._clean_status(data.get('status'), RequestStatus) or RequestStatus.PENDING,
                    'branch_manager_approval': self._clean_status(data.get('branch_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    'department_manager_approval': self._clean_status(data.get('department_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    'manager_approval': self._clean_status(data.get('manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    'approval_notes': data.get('approval_notes'),
                    'uploaded_by_id': self._get_user_id(data.get('uploaded_by')) or self.admin_user.id,
                    'assigned_to_id': self._get_user_id(data.get('assigned_to')),
                }
                ts = self._parse_datetime(data.get('created_at'))
                result = self._save_record(AttendanceRecord, record_id, defaults, 'created_at', ts)
                self.stats[result] += 1
            except Exception as e:
                self.stats['errors'] += 1
                if self.stats['errors'] == 1:
                    self.stderr.write(f"   ERR: {e}")
        self._print_stats('سجلات الحضور')

    # ==============================
    # Messages
    # ==============================
    def _import_messages(self, content):
        self.stdout.write("\nاستيراد الرسائل...")
        self._reset_stats()
        cols = self._extract_columns(content, 'messages')
        if not cols:
            self.stdout.write("   لا توجد بيانات")
            return
        for row_str in self._extract_rows(content, 'messages'):
            try:
                values = self._parse_row_values(row_str)
                values += [None] * (len(cols) - len(values))
                data = dict(zip(cols, values))
                record_id = data['id']
                sender = self._get_user(data.get('sender_id'))
                receiver = self._get_user(data.get('receiver_id'))
                reply_by = self._get_user(data.get('reply_by'))
                if not sender or not receiver:
                    self.stats['errors'] += 1
                    continue
                defaults = {
                    'sender': sender,
                    'receiver': receiver,
                    'message_text': str(data.get('message_text') or '').replace('\r\n', '\n'),
                    'status': data.get('status') or 'open',
                    'reply_text': data.get('reply_text'),
                    'reply_by': reply_by,
                    'reply_at': self._parse_datetime(data.get('reply_at')),
                    'reply_file_path': data.get('reply_file_path'),
                }
                ts = self._parse_datetime(data.get('sent_at'))
                result = self._save_record(UserMessage, record_id, defaults, 'sent_at', ts)
                self.stats[result] += 1
            except Exception as e:
                self.stats['errors'] += 1
        self._print_stats('الرسائل')

    # ==============================
    # Sync files to R2
    # ==============================
    def _sync_files_to_r2(self):
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("رفع الملفات الجديدة إلى R2...")
        try:
            from django.conf import settings
            import subprocess
            upload_script = Path(settings.BASE_DIR) / 'upload_to_r2.py'
            if upload_script.exists():
                result = subprocess.run(
                    [sys.executable, str(upload_script)],
                    capture_output=True, text=True, cwd=str(settings.BASE_DIR)
                )
                self.stdout.write(result.stdout)
                if result.returncode != 0:
                    self.stderr.write(f"خطأ في رفع الملفات: {result.stderr}")
            else:
                self.stdout.write("   سكريبت upload_to_r2.py غير موجود")
        except Exception as e:
            self.stderr.write(f"   خطأ: {e}")

    # ==============================
    # Summary
    # ==============================
    def _print_summary(self):
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("ملخص الاستيراد التزايدي:")
        self.stdout.write("=" * 60)
        t = self.total_stats
        self.stdout.write(f"   جديد: {t['imported']}")
        if self.update_mode:
            self.stdout.write(f"   محدّث: {t['updated']}")
        self.stdout.write(f"   موجود (متخطى): {t['skipped']}")
        self.stdout.write(f"   أخطاء: {t['errors']}")
        self.stdout.write("")
        self.stdout.write("عدد السجلات الحالية:")
        for model, name in [
            (Branch, 'الفروع'), (CostCenter, 'مراكز التكلفة'),
            (Organization, 'المؤسسات'), (Sponsorship, 'الكفالات'),
            (EmployeeFile, 'الموظفين'), (AdvanceFile, 'السلف'),
            (StatementFile, 'البيانات/الإجازات'), (ViolationFile, 'المخالفات'),
            (TerminationFile, 'إنهاء الخدمات'), (MedicalInsurance, 'التأمين الطبي'),
            (MedicalExcuse, 'الأعذار الطبية'), (SalaryAdjustment, 'تعديلات الرواتب'),
            (EmployeeTransferRequest, 'طلبات النقل'), (AttendanceRecord, 'سجلات الحضور'),
            (UserMessage, 'الرسائل'),
        ]:
            self.stdout.write(f"   {name}: {model.objects.count()}")
        self.stdout.write("=" * 60)
        self.stdout.write("تم بنجاح!")
