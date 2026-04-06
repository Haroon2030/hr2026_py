"""
استيراد البيانات من ملف SQL القديم (MySQL/PHP) إلى Django
=========================================================
الاستخدام:
    python manage.py import_from_sql
    python manage.py import_from_sql --clean   # مسح البيانات القديمة أولاً
    python manage.py import_from_sql --file /path/to/file.sql
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
    help = 'استيراد البيانات من ملف SQL القديم'

    def add_arguments(self, parser):
        parser.add_argument('--clean', action='store_true', help='مسح البيانات القديمة أولاً')
        parser.add_argument('--file', type=str, help='مسار ملف SQL', default=None)

    def handle(self, *args, **options):
        self.admin_user = User.objects.filter(is_superuser=True).first() or User.objects.first()
        if not self.admin_user:
            self.stderr.write("لا يوجد مستخدمين!")
            return

        self.branch_cache: Dict[str, Branch] = {}
        self.cost_center_cache: Dict[str, CostCenter] = {}
        self.user_cache: Dict[int, Any] = {}
        self.stats = {'imported': 0, 'skipped': 0, 'errors': 0}

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
            self.stderr.write(f"ملف SQL غير موجود! جرب: --file /path/to/file.sql")
            self.stderr.write(f"المسارات المفحوصة: {[str(c) for c in candidates]}")
            return

        self.stdout.write("=" * 60)
        self.stdout.write("         استيراد شامل لبيانات HR Pro")
        self.stdout.write("=" * 60)
        self.stdout.write(f"المستخدم: {self.admin_user}")
        self.stdout.write(f"الملف: {sql_file}")

        if options['clean']:
            self._clean_data()

        with open(sql_file, 'r', encoding='utf-8') as f:
            content = f.read()
        self.stdout.write(f"حجم الملف: {len(content):,} حرف")

        # استيراد البيانات
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

    # ==============================
    # SQL Parsing
    # ==============================
    def _parse_sql_value(self, v: str) -> Any:
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

    def _parse_row_values(self, row_str: str) -> List[Any]:
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

    def _extract_rows(self, content: str, table_name: str) -> List[str]:
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

    def _extract_columns(self, content: str, table_name: str) -> List[str]:
        pattern = rf"INSERT INTO `{table_name}`\s*\(([^)]+)\)\s*VALUES"
        match = re.search(pattern, content)
        if not match:
            return []
        return re.findall(r'`([^`]+)`', match.group(1))

    # ==============================
    # Helper functions
    # ==============================
    def _reset_stats(self):
        self.stats = {'imported': 0, 'skipped': 0, 'errors': 0}

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
    # Import functions
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
                    if model_class.objects.filter(pk=record_id).exists() or model_class.objects.filter(name=name).exists():
                        self.stats['skipped'] += 1
                    else:
                        try:
                            model_class.objects.create(id=record_id, name=name)
                            self.stats['imported'] += 1
                        except Exception:
                            self.stats['errors'] += 1
                else:
                    self.stats['skipped'] += 1
        self.stdout.write(f"   OK {self.stats['imported']} | SKIP {self.stats['skipped']} | ERR {self.stats['errors']}")

    def _import_branches(self, content):
        self._import_simple(content, 'branches', Branch, 'استيراد الفروع')

    def _import_cost_centers(self, content):
        self._import_simple(content, 'cost_centers', CostCenter, 'استيراد مراكز التكلفة')

    def _import_organizations(self, content):
        self._import_simple(content, 'organizations', Organization, 'استيراد المؤسسات')

    def _import_sponsorships(self, content):
        self._import_simple(content, 'sponsorships', Sponsorship, 'استيراد الكفالات')

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
                if EmployeeFile.objects.filter(pk=record_id).exists():
                    self.stats['skipped'] += 1
                    continue
                start_type_val = str(data.get('start_type') or '').lower()
                start_type = StartType.REPLACEMENT if start_type_val in ['transfer', 'نقل', 'replacement', 'بديل'] else StartType.NEW
                obj = EmployeeFile(
                    id=record_id,
                    employee_name=str(data['employee_name'] or ''),
                    employee_number=str(data.get('employee_number') or '') or None,
                    national_id=str(data.get('national_id') or '') or None,
                    nationality=str(data.get('nationality') or '') or None,
                    department=str(data.get('department') or '') or None,
                    start_type=start_type,
                    start_date=self._parse_date(data.get('start_date')),
                    salary=self._to_decimal(data.get('salary')),
                    branch=self._get_or_create_branch(data.get('branch')),
                    department_filter=data.get('department_filter'),
                    cost_center=self._get_or_create_cost_center(data.get('cost_center')),
                    notes=data.get('notes'),
                    file_path=data.get('file_path') or '',
                    file_name=data.get('file_name') or data.get('original_filename'),
                    status=self._clean_status(data.get('status'), RequestStatus) or RequestStatus.PENDING,
                    branch_manager_approval=self._clean_status(data.get('branch_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    department_manager_approval=self._clean_status(data.get('department_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    manager_approval=self._clean_status(data.get('manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    approval_notes=data.get('approval_notes'),
                    uploaded_by_id=self._get_user_id(data.get('uploaded_by')) or self.admin_user.id,
                    assigned_to_id=self._get_user_id(data.get('assigned_to')),
                    completed_by_id=self._get_user_id(data.get('completed_by')),
                    branch_approved_by_id=self._get_user_id(data.get('branch_approved_by')),
                    department_approved_by_id=self._get_user_id(data.get('department_approved_by')),
                    manager_approved_by_id=self._get_user_id(data.get('manager_approved_by')),
                    assigned_employee_number=data.get('assigned_employee_number'),
                )
                obj.save()
                created_at = self._parse_datetime(data.get('created_at'))
                if created_at:
                    EmployeeFile.objects.filter(pk=record_id).update(created_at=created_at)
                self.stats['imported'] += 1
            except Exception as e:
                self.stats['errors'] += 1
                if self.stats['errors'] <= 3:
                    self.stderr.write(f"   ERR ID {data.get('id')}: {e}")
        self.stdout.write(f"   OK {self.stats['imported']} | SKIP {self.stats['skipped']} | ERR {self.stats['errors']}")

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
                if AdvanceFile.objects.filter(pk=record_id).exists():
                    self.stats['skipped'] += 1
                    continue
                obj = AdvanceFile(
                    id=record_id,
                    employee_name=str(data['employee_name'] or ''),
                    employee_number=str(data.get('employee_number') or '') or None,
                    advance_amount=self._to_decimal(data.get('advance_amount')),
                    advance_date=self._parse_date(data.get('advance_date')),
                    file_path=data.get('file_path') or '',
                    file_name=data.get('file_name') or data.get('original_filename'),
                    notes=data.get('notes'),
                    status=self._clean_status(data.get('status'), RequestStatus) or RequestStatus.PENDING,
                    branch=self._get_or_create_branch(data.get('branch')),
                    department_filter=data.get('department_filter'),
                    installments=self._to_int(data.get('installments')) or 1,
                    branch_manager_approval=self._clean_status(data.get('branch_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    department_manager_approval=self._clean_status(data.get('department_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    manager_approval=self._clean_status(data.get('manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    approval_notes=data.get('approval_notes'),
                    uploaded_by_id=self._get_user_id(data.get('uploaded_by')) or self.admin_user.id,
                    assigned_to_id=self._get_user_id(data.get('assigned_to')),
                    completed_by_id=self._get_user_id(data.get('completed_by')),
                    branch_approved_by_id=self._get_user_id(data.get('branch_approved_by')),
                    department_approved_by_id=self._get_user_id(data.get('department_approved_by')),
                    manager_approved_by_id=self._get_user_id(data.get('manager_approved_by')),
                )
                obj.save()
                created_at = self._parse_datetime(data.get('created_at'))
                if created_at:
                    AdvanceFile.objects.filter(pk=record_id).update(created_at=created_at)
                self.stats['imported'] += 1
            except Exception as e:
                self.stats['errors'] += 1
        self.stdout.write(f"   OK {self.stats['imported']} | SKIP {self.stats['skipped']} | ERR {self.stats['errors']}")

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
                if StatementFile.objects.filter(pk=record_id).exists():
                    self.stats['skipped'] += 1
                    continue
                obj = StatementFile(
                    id=record_id,
                    employee_name=str(data['employee_name'] or ''),
                    employee_number=str(data.get('employee_number') or '') or None,
                    statement_type=str(data.get('statement_type') or ''),
                    file_path=data.get('file_path') or '',
                    file_name=data.get('file_name') or data.get('original_filename'),
                    notes=data.get('notes'),
                    status=self._clean_status(data.get('status'), RequestStatus) or RequestStatus.PENDING,
                    branch=self._get_or_create_branch(data.get('branch')),
                    department_filter=data.get('department_filter'),
                    vacation_days=self._to_int(data.get('vacation_days')),
                    vacation_start=self._parse_date(data.get('vacation_start')),
                    vacation_end=self._parse_date(data.get('vacation_end')),
                    vacation_balance=self._to_decimal(data.get('vacation_balance')),
                    branch_manager_approval=self._clean_status(data.get('branch_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    department_manager_approval=self._clean_status(data.get('department_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    manager_approval=self._clean_status(data.get('manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    approval_notes=data.get('approval_notes'),
                    uploaded_by_id=self._get_user_id(data.get('uploaded_by')) or self.admin_user.id,
                    assigned_to_id=self._get_user_id(data.get('assigned_to')),
                    completed_by_id=self._get_user_id(data.get('completed_by')),
                    branch_approved_by_id=self._get_user_id(data.get('branch_approved_by')),
                    department_approved_by_id=self._get_user_id(data.get('department_approved_by')),
                    manager_approved_by_id=self._get_user_id(data.get('manager_approved_by')),
                )
                obj.save()
                created_at = self._parse_datetime(data.get('created_at'))
                if created_at:
                    StatementFile.objects.filter(pk=record_id).update(created_at=created_at)
                self.stats['imported'] += 1
            except Exception as e:
                self.stats['errors'] += 1
                if self.stats['errors'] == 1:
                    self.stderr.write(f"   ERR: {e}")
        self.stdout.write(f"   OK {self.stats['imported']} | SKIP {self.stats['skipped']} | ERR {self.stats['errors']}")

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
                if ViolationFile.objects.filter(pk=record_id).exists():
                    self.stats['skipped'] += 1
                    continue
                obj = ViolationFile(
                    id=record_id,
                    employee_name=str(data['employee_name'] or ''),
                    employee_number=str(data.get('employee_number') or '') or None,
                    violation_type=str(data.get('violation_type') or ''),
                    violation_date=self._parse_date(data.get('violation_date')),
                    file_path=data.get('file_path') or '',
                    violation_notes=data.get('violation_notes'),
                    employee_statement=data.get('employee_statement'),
                    status=self._clean_status(data.get('status'), RequestStatus) or RequestStatus.PENDING,
                    branch=self._get_or_create_branch(data.get('branch')),
                    employee_branch=self._get_or_create_branch(data.get('employee_branch')),
                    employee_department=data.get('employee_department'),
                    department_filter=data.get('department_filter'),
                    branch_manager_approval=self._clean_status(data.get('branch_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    department_manager_approval=self._clean_status(data.get('department_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    manager_approval=self._clean_status(data.get('manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    approval_notes=data.get('approval_notes'),
                    uploaded_by_id=self._get_user_id(data.get('uploaded_by')) or self.admin_user.id,
                    assigned_to_id=self._get_user_id(data.get('assigned_to')),
                    branch_approved_by_id=self._get_user_id(data.get('branch_approved_by')),
                    department_approved_by_id=self._get_user_id(data.get('department_approved_by')),
                    manager_approved_by_id=self._get_user_id(data.get('manager_approved_by')),
                )
                obj.save()
                created_at = self._parse_datetime(data.get('uploaded_at'))
                if created_at:
                    ViolationFile.objects.filter(pk=record_id).update(created_at=created_at)
                self.stats['imported'] += 1
            except Exception as e:
                self.stats['errors'] += 1
                if self.stats['errors'] == 1:
                    self.stderr.write(f"   ERR: {e}")
        self.stdout.write(f"   OK {self.stats['imported']} | SKIP {self.stats['skipped']} | ERR {self.stats['errors']}")

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
                if TerminationFile.objects.filter(pk=record_id).exists():
                    self.stats['skipped'] += 1
                    continue
                obj = TerminationFile(
                    id=record_id,
                    employee_name=str(data['employee_name'] or ''),
                    employee_number=str(data.get('employee_number') or '') or None,
                    national_id=str(data.get('national_id') or '') or None,
                    nationality=str(data.get('nationality') or '') or None,
                    notes=data.get('notes'),
                    file_path=data.get('file_path') or '',
                    status=self._clean_status(data.get('status'), RequestStatus) or RequestStatus.PENDING,
                    branch=self._get_or_create_branch(data.get('branch')),
                    department_filter=data.get('department_filter'),
                    branch_manager_approval=self._clean_status(data.get('branch_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    department_manager_approval=self._clean_status(data.get('department_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    manager_approval=self._clean_status(data.get('manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    approval_notes=data.get('approval_notes'),
                    uploaded_by_id=self._get_user_id(data.get('uploaded_by')) or self.admin_user.id,
                    assigned_to_id=self._get_user_id(data.get('assigned_to')),
                    branch_approved_by_id=self._get_user_id(data.get('branch_approved_by')),
                    department_approved_by_id=self._get_user_id(data.get('department_approved_by')),
                    manager_approved_by_id=self._get_user_id(data.get('manager_approved_by')),
                )
                obj.save()
                created_at = self._parse_datetime(data.get('created_at'))
                if created_at:
                    TerminationFile.objects.filter(pk=record_id).update(created_at=created_at)
                self.stats['imported'] += 1
            except Exception as e:
                self.stats['errors'] += 1
        self.stdout.write(f"   OK {self.stats['imported']} | SKIP {self.stats['skipped']} | ERR {self.stats['errors']}")

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
                if MedicalInsurance.objects.filter(pk=record_id).exists():
                    self.stats['skipped'] += 1
                    continue
                obj = MedicalInsurance(
                    id=record_id,
                    employee_name=str(data['employee_name'] or ''),
                    insurance_type=str(data.get('insurance_type') or ''),
                    details=str(data.get('details') or ''),
                    file_path=data.get('file_path') or '',
                    status=self._clean_status(data.get('status'), RequestStatus) or RequestStatus.PENDING,
                    branch=self._get_or_create_branch(data.get('branch')),
                    department_filter=data.get('department_filter'),
                    branch_manager_approval=self._clean_status(data.get('branch_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    department_manager_approval=self._clean_status(data.get('department_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    manager_approval=self._clean_status(data.get('manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    approval_notes=data.get('approval_notes'),
                    uploaded_by_id=self._get_user_id(data.get('uploaded_by')) or self.admin_user.id,
                    assigned_to_id=self._get_user_id(data.get('assigned_to')),
                    branch_approved_by_id=self._get_user_id(data.get('branch_approved_by')),
                    department_approved_by_id=self._get_user_id(data.get('department_approved_by')),
                    manager_approved_by_id=self._get_user_id(data.get('manager_approved_by')),
                )
                obj.save()
                created_at = self._parse_datetime(data.get('uploaded_at'))
                if created_at:
                    MedicalInsurance.objects.filter(pk=record_id).update(created_at=created_at)
                self.stats['imported'] += 1
            except Exception as e:
                self.stats['errors'] += 1
                if self.stats['errors'] == 1:
                    self.stderr.write(f"   ERR: {e}")
        self.stdout.write(f"   OK {self.stats['imported']} | SKIP {self.stats['skipped']} | ERR {self.stats['errors']}")

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
                if MedicalExcuse.objects.filter(pk=record_id).exists():
                    self.stats['skipped'] += 1
                    continue
                obj = MedicalExcuse(
                    id=record_id,
                    employee_name=str(data['employee_name'] or ''),
                    employee_id_number=str(data.get('employee_id') or ''),
                    branch=str(data.get('branch') or ''),
                    department=str(data.get('department') or ''),
                    cost_center=self._get_or_create_cost_center(data.get('cost_center')),
                    excuse_reason=str(data.get('excuse_reason') or ''),
                    excuse_date=self._parse_date(data.get('excuse_date')),
                    excuse_duration=self._to_int(data.get('excuse_duration')) or 1,
                    file_path=data.get('file_path') or '',
                    status=self._clean_status(data.get('status'), RequestStatus) or RequestStatus.PENDING,
                    department_filter=data.get('department_filter'),
                    branch_manager_approval=self._clean_status(data.get('branch_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    department_manager_approval=self._clean_status(data.get('department_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    manager_approval=self._clean_status(data.get('manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    approval_notes=data.get('approval_notes'),
                    uploaded_by_id=self._get_user_id(data.get('uploaded_by')) or self.admin_user.id,
                    assigned_to_id=self._get_user_id(data.get('assigned_to')),
                    branch_approved_by_id=self._get_user_id(data.get('branch_approved_by')),
                    department_approved_by_id=self._get_user_id(data.get('department_approved_by')),
                    manager_approved_by_id=self._get_user_id(data.get('manager_approved_by')),
                )
                obj.save()
                created_at = self._parse_datetime(data.get('created_at'))
                if created_at:
                    MedicalExcuse.objects.filter(pk=record_id).update(created_at=created_at)
                self.stats['imported'] += 1
            except Exception as e:
                self.stats['errors'] += 1
                if self.stats['errors'] == 1:
                    self.stderr.write(f"   ERR: {e}")
        self.stdout.write(f"   OK {self.stats['imported']} | SKIP {self.stats['skipped']} | ERR {self.stats['errors']}")

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
                if SalaryAdjustment.objects.filter(pk=record_id).exists():
                    self.stats['skipped'] += 1
                    continue
                obj = SalaryAdjustment(
                    id=record_id,
                    employee_name=str(data['employee_name'] or ''),
                    employee_number=str(data.get('employee_number') or ''),
                    department=str(data.get('department') or ''),
                    current_salary=self._to_decimal(data.get('current_salary')),
                    salary_increase=self._to_decimal(data.get('salary_increase')),
                    new_salary=self._to_decimal(data.get('new_salary')),
                    adjustment_reason=data.get('adjustment_reason'),
                    notes=data.get('notes'),
                    status=self._clean_status(data.get('status'), RequestStatus) or RequestStatus.PENDING,
                    branch=self._get_or_create_branch(data.get('branch')),
                    cost_center=self._get_or_create_cost_center(data.get('cost_center')),
                    department_filter=data.get('department_filter'),
                    branch_manager_approval=self._clean_status(data.get('branch_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    department_manager_approval=self._clean_status(data.get('department_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    manager_approval=self._clean_status(data.get('manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    approval_notes=data.get('approval_notes'),
                    uploaded_by_id=self._get_user_id(data.get('uploaded_by')) or self.admin_user.id,
                    assigned_to_id=self._get_user_id(data.get('assigned_to')),
                    branch_approved_by_id=self._get_user_id(data.get('branch_approved_by')),
                    department_approved_by_id=self._get_user_id(data.get('department_approved_by')),
                    manager_approved_by_id=self._get_user_id(data.get('manager_approved_by')),
                )
                obj.save()
                created_at = self._parse_datetime(data.get('created_at'))
                if created_at:
                    SalaryAdjustment.objects.filter(pk=record_id).update(created_at=created_at)
                self.stats['imported'] += 1
            except Exception as e:
                self.stats['errors'] += 1
                if self.stats['errors'] == 1:
                    self.stderr.write(f"   ERR: {e}")
        self.stdout.write(f"   OK {self.stats['imported']} | SKIP {self.stats['skipped']} | ERR {self.stats['errors']}")

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
                if EmployeeTransferRequest.objects.filter(pk=record_id).exists():
                    self.stats['skipped'] += 1
                    continue
                obj = EmployeeTransferRequest(
                    id=record_id,
                    employee_name=str(data['employee_name'] or ''),
                    employee_id_number=str(data.get('employee_id') or ''),
                    current_branch=self._get_or_create_branch(data.get('current_branch')),
                    requested_branch=self._get_or_create_branch(data.get('requested_branch')),
                    current_department=str(data.get('current_department') or ''),
                    requested_department=str(data.get('requested_department') or ''),
                    department_filter=data.get('department_filter'),
                    current_cost_center=self._get_or_create_cost_center(data.get('current_cost_center')),
                    new_cost_center=self._get_or_create_cost_center(data.get('new_cost_center')),
                    transfer_reason=str(data.get('transfer_reason') or ''),
                    preferred_date=self._parse_date(data.get('preferred_date')),
                    status=self._clean_status(data.get('status'), RequestStatus) or RequestStatus.PENDING,
                    assign_note=data.get('assign_note'),
                    in_progress_at=self._parse_datetime(data.get('in_progress_at')),
                    completed_at=self._parse_datetime(data.get('completed_at')),
                    branch_manager_approval=self._clean_status(data.get('branch_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    department_manager_approval=self._clean_status(data.get('department_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    manager_approval=self._clean_status(data.get('manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    approval_notes=data.get('approval_notes'),
                    uploaded_by_id=self._get_user_id(data.get('uploaded_by')) or self.admin_user.id,
                    assigned_to_id=self._get_user_id(data.get('assigned_to')),
                    completed_by_id=self._get_user_id(data.get('completed_by')),
                    branch_approved_by_id=self._get_user_id(data.get('branch_approved_by')),
                    department_approved_by_id=self._get_user_id(data.get('department_approved_by')),
                    manager_approved_by_id=self._get_user_id(data.get('manager_approved_by')),
                )
                obj.save()
                created_at = self._parse_datetime(data.get('created_at'))
                if created_at:
                    EmployeeTransferRequest.objects.filter(pk=record_id).update(created_at=created_at)
                self.stats['imported'] += 1
            except Exception as e:
                self.stats['errors'] += 1
                if self.stats['errors'] == 1:
                    self.stderr.write(f"   ERR: {e}")
        self.stdout.write(f"   OK {self.stats['imported']} | SKIP {self.stats['skipped']} | ERR {self.stats['errors']}")

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
                if AttendanceRecord.objects.filter(pk=record_id).exists():
                    self.stats['skipped'] += 1
                    continue
                obj = AttendanceRecord(
                    id=record_id,
                    batch_id=str(data.get('batch_id') or ''),
                    batch_date=self._parse_date(data.get('batch_date')),
                    employee_name=str(data['employee_name'] or ''),
                    title=data.get('title'),
                    branch=self._get_or_create_branch(data.get('branch')),
                    department_filter=data.get('department_filter'),
                    date_from=self._parse_date(data.get('date_from')),
                    nationality=data.get('nationality'),
                    shift_start=data.get('shift_start'),
                    shift_end=data.get('shift_end'),
                    attendance_date=self._parse_date(data.get('attendance_date')),
                    notes=data.get('notes'),
                    status=self._clean_status(data.get('status'), RequestStatus) or RequestStatus.PENDING,
                    branch_manager_approval=self._clean_status(data.get('branch_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    department_manager_approval=self._clean_status(data.get('department_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    manager_approval=self._clean_status(data.get('manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                    approval_notes=data.get('approval_notes'),
                    uploaded_by_id=self._get_user_id(data.get('uploaded_by')) or self.admin_user.id,
                    assigned_to_id=self._get_user_id(data.get('assigned_to')),
                )
                obj.save()
                created_at = self._parse_datetime(data.get('created_at'))
                if created_at:
                    AttendanceRecord.objects.filter(pk=record_id).update(created_at=created_at)
                self.stats['imported'] += 1
            except Exception as e:
                self.stats['errors'] += 1
                if self.stats['errors'] == 1:
                    self.stderr.write(f"   ERR: {e}")
        self.stdout.write(f"   OK {self.stats['imported']} | SKIP {self.stats['skipped']} | ERR {self.stats['errors']}")

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
                if UserMessage.objects.filter(pk=record_id).exists():
                    self.stats['skipped'] += 1
                    continue
                sender = self._get_user(data.get('sender_id'))
                receiver = self._get_user(data.get('receiver_id'))
                reply_by = self._get_user(data.get('reply_by'))
                if not sender or not receiver:
                    self.stats['errors'] += 1
                    continue
                obj = UserMessage(
                    id=record_id,
                    sender=sender,
                    receiver=receiver,
                    message_text=str(data.get('message_text') or '').replace('\r\n', '\n'),
                    status=data.get('status') or 'open',
                    reply_text=data.get('reply_text'),
                    reply_by=reply_by,
                    reply_at=self._parse_datetime(data.get('reply_at')),
                    reply_file_path=data.get('reply_file_path'),
                )
                obj.save()
                sent_at = self._parse_datetime(data.get('sent_at'))
                if sent_at:
                    UserMessage.objects.filter(pk=record_id).update(sent_at=sent_at)
                self.stats['imported'] += 1
            except Exception as e:
                self.stats['errors'] += 1
        self.stdout.write(f"   OK {self.stats['imported']} | SKIP {self.stats['skipped']} | ERR {self.stats['errors']}")

    def _print_summary(self):
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("ملخص البيانات:")
        self.stdout.write("=" * 60)
        self.stdout.write(f"   الفروع: {Branch.objects.count()}")
        self.stdout.write(f"   مراكز التكلفة: {CostCenter.objects.count()}")
        self.stdout.write(f"   المؤسسات: {Organization.objects.count()}")
        self.stdout.write(f"   الكفالات: {Sponsorship.objects.count()}")
        self.stdout.write(f"   الموظفين: {EmployeeFile.objects.count()}")
        self.stdout.write(f"   السلف: {AdvanceFile.objects.count()}")
        self.stdout.write(f"   البيانات/الإجازات: {StatementFile.objects.count()}")
        self.stdout.write(f"   المخالفات: {ViolationFile.objects.count()}")
        self.stdout.write(f"   إنهاء الخدمات: {TerminationFile.objects.count()}")
        self.stdout.write(f"   التأمين الطبي: {MedicalInsurance.objects.count()}")
        self.stdout.write(f"   الأعذار الطبية: {MedicalExcuse.objects.count()}")
        self.stdout.write(f"   تعديلات الرواتب: {SalaryAdjustment.objects.count()}")
        self.stdout.write(f"   طلبات النقل: {EmployeeTransferRequest.objects.count()}")
        self.stdout.write(f"   سجلات الحضور: {AttendanceRecord.objects.count()}")
        self.stdout.write(f"   الرسائل: {UserMessage.objects.count()}")
        self.stdout.write("=" * 60)
        self.stdout.write("تم الاستيراد بنجاح!")
