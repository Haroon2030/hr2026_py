#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
استيراد شامل لجميع البيانات من SQL dump
========================================
يستورد جميع الجداول من ملف SQL بدون مشاكل

الاستخدام:
    cd django_hr
    python import_all_data.py

الميزات:
- يتخطى السجلات الموجودة مسبقاً (آمن للتشغيل المتكرر)
- يعالج الأخطاء ويستمر
- يظهر تقدم مفصل
"""
import os
import sys
import re
import io
import django
from pathlib import Path
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone as dt_timezone
from typing import Any, Dict, List, Optional

# Fix encoding for Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ==============================
# إعداد Django
# ==============================
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hr_project.settings')
django.setup()

from django.db import models
from django.contrib.auth import get_user_model
from apps.core.models import (
    EmployeeFile, AdvanceFile, StatementFile, ViolationFile,
    TerminationFile, MedicalInsurance, MedicalExcuse,
    SalaryAdjustment, EmployeeTransferRequest, AttendanceRecord,
    RequestStatus, ApprovalStatus, StartType,
    Branch, CostCenter, Organization, Sponsorship,
    UserMessage, MessageStatus,
)

User = get_user_model()

# ==============================
# متغيرات عامة
# ==============================
SQL_FILE = Path(__file__).parent.parent / 'u824688047_hr_pro.sql'
admin_user = None
branch_cache: Dict[str, Branch] = {}
cost_center_cache: Dict[str, CostCenter] = {}
user_cache: Dict[int, Any] = {}

# ==============================
# إحصائيات
# ==============================
stats = {
    'imported': 0,
    'skipped': 0,
    'errors': 0,
}


def reset_stats():
    stats['imported'] = 0
    stats['skipped'] = 0
    stats['errors'] = 0


# ==============================
# دوال SQL Parsing
# ==============================

def parse_sql_value(v: str) -> Any:
    """تحويل قيمة SQL إلى قيمة Python"""
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


def parse_row_values(row_str: str) -> List[Any]:
    """تحليل صف SQL"""
    values, current, in_quote = [], "", False
    for i, char in enumerate(row_str):
        if char == "'" and (i == 0 or row_str[i-1] != '\\'):
            in_quote = not in_quote
            current += char
        elif char == ',' and not in_quote:
            values.append(parse_sql_value(current.strip()))
            current = ""
        else:
            current += char
    if current.strip():
        values.append(parse_sql_value(current.strip()))
    return values


def extract_rows(content: str, table_name: str) -> List[str]:
    """استخراج صفوف INSERT من الجدول - يدعم INSERT متعددة"""
    # البحث عن جميع INSERT statements
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


def extract_columns(content: str, table_name: str) -> List[str]:
    """استخراج أسماء الأعمدة من INSERT statement"""
    # البحث عن INSERT INTO `table` (`col1`, `col2`, ...) VALUES
    pattern = rf"INSERT INTO `{table_name}`\s*\(([^)]+)\)\s*VALUES"
    match = re.search(pattern, content)
    if not match:
        return []
    
    cols_str = match.group(1)
    # استخراج أسماء الأعمدة
    cols = re.findall(r'`([^`]+)`', cols_str)
    return cols


# ==============================
# دوال مساعدة
# ==============================

def parse_datetime(val: Any) -> Optional[datetime]:
    if not val or not isinstance(val, str):
        return None
    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d']:
        try:
            return datetime.strptime(val.strip(), fmt).replace(tzinfo=dt_timezone.utc)
        except ValueError:
            continue
    return None


def parse_date(val: Any):
    if not val or not isinstance(val, str):
        return None
    try:
        return datetime.strptime(val.strip(), '%Y-%m-%d').date()
    except ValueError:
        return None


def get_user(user_id: Any):
    """جلب المستخدم بالـ ID مع cache"""
    if not user_id:
        return None
    try:
        uid = int(user_id)
        if uid not in user_cache:
            try:
                user_cache[uid] = User.objects.get(pk=uid)
            except User.DoesNotExist:
                user_cache[uid] = None
        return user_cache[uid]
    except (ValueError, TypeError):
        return None


def get_user_id(val: Any) -> Optional[int]:
    user = get_user(val)
    return user.id if user else None


def clean_status(val: Any, choices_class) -> Optional[str]:
    if not val:
        return None
    val = str(val).strip().lower()
    valid = [c[0] for c in choices_class.choices]
    return val if val in valid else None


def to_decimal(v: Any) -> Decimal:
    try:
        return Decimal(str(v or 0))
    except (InvalidOperation, ValueError):
        return Decimal('0')


def to_int(v: Any) -> int:
    try:
        return int(v) if v else 0
    except (ValueError, TypeError):
        return 0


def get_or_create_branch(name: Any) -> Optional[Branch]:
    if not name:
        return None
    name = str(name).strip()
    if not name:
        return None
    if name not in branch_cache:
        branch, _ = Branch.objects.get_or_create(name=name)
        branch_cache[name] = branch
    return branch_cache[name]


def get_or_create_cost_center(name: Any) -> Optional[CostCenter]:
    if not name:
        return None
    name = str(name).strip()
    if not name:
        return None
    if name not in cost_center_cache:
        cc, _ = CostCenter.objects.get_or_create(name=name)
        cost_center_cache[name] = cc
    return cost_center_cache[name]


# ==============================
# دوال الاستيراد
# ==============================

def import_branches(content: str):
    """استيراد الفروع"""
    print("\n📍 استيراد الفروع...")
    reset_stats()
    
    for row_str in extract_rows(content, 'branches'):
        values = parse_row_values(row_str)
        if len(values) >= 2:
            record_id, name = values[0], values[1]
            if name:
                name = str(name).strip()
                # تحقق من وجود السجل بالـ ID أو الاسم
                if Branch.objects.filter(pk=record_id).exists() or Branch.objects.filter(name=name).exists():
                    stats['skipped'] += 1
                else:
                    try:
                        Branch.objects.create(id=record_id, name=name)
                        stats['imported'] += 1
                    except Exception:
                        stats['errors'] += 1
            else:
                stats['skipped'] += 1
    
    print(f"   [OK] {stats['imported']} | SKIP  {stats['skipped']} | ERR {stats['errors']}")


def import_cost_centers(content: str):
    """استيراد مراكز التكلفة"""
    print("\n📍 استيراد مراكز التكلفة...")
    reset_stats()
    
    for row_str in extract_rows(content, 'cost_centers'):
        values = parse_row_values(row_str)
        if len(values) >= 2:
            record_id, name = values[0], values[1]
            if name:
                name = str(name).strip()
                if CostCenter.objects.filter(pk=record_id).exists() or CostCenter.objects.filter(name=name).exists():
                    stats['skipped'] += 1
                else:
                    try:
                        CostCenter.objects.create(id=record_id, name=name)
                        stats['imported'] += 1
                    except Exception:
                        stats['errors'] += 1
            else:
                stats['skipped'] += 1
    
    print(f"   [OK] {stats['imported']} | SKIP  {stats['skipped']} | ERR {stats['errors']}")


def import_organizations(content: str):
    """استيراد المؤسسات"""
    print("\n📍 استيراد المؤسسات...")
    reset_stats()
    
    for row_str in extract_rows(content, 'organizations'):
        values = parse_row_values(row_str)
        if len(values) >= 2:
            record_id, name = values[0], values[1]
            if name:
                name = str(name).strip()
                if Organization.objects.filter(pk=record_id).exists() or Organization.objects.filter(name=name).exists():
                    stats['skipped'] += 1
                else:
                    try:
                        Organization.objects.create(id=record_id, name=name)
                        stats['imported'] += 1
                    except Exception:
                        stats['errors'] += 1
            else:
                stats['skipped'] += 1
    
    print(f"   [OK] {stats['imported']} | SKIP  {stats['skipped']} | ERR {stats['errors']}")


def import_sponsorships(content: str):
    """استيراد الكفالات"""
    print("\n📍 استيراد الكفالات...")
    reset_stats()
    
    for row_str in extract_rows(content, 'sponsorships'):
        values = parse_row_values(row_str)
        if len(values) >= 2:
            record_id, name = values[0], values[1]
            if name:
                name = str(name).strip()
                if Sponsorship.objects.filter(pk=record_id).exists() or Sponsorship.objects.filter(name=name).exists():
                    stats['skipped'] += 1
                else:
                    try:
                        Sponsorship.objects.create(id=record_id, name=name)
                        stats['imported'] += 1
                    except Exception:
                        stats['errors'] += 1
            else:
                stats['skipped'] += 1
    
    print(f"   [OK] {stats['imported']} | SKIP  {stats['skipped']} | ERR {stats['errors']}")


def import_employees(content: str):
    """استيراد الموظفين"""
    print("\n[EMPLOYEES] استيراد الموظفين...")
    reset_stats()
    
    cols = extract_columns(content, 'employee_files')
    if not cols:
        print("   No data found")
        return
    
    for row_str in extract_rows(content, 'employee_files'):
        try:
            values = parse_row_values(row_str)
            values += [None] * (len(cols) - len(values))
            data = dict(zip(cols, values))
            
            record_id = data['id']
            if EmployeeFile.objects.filter(pk=record_id).exists():
                stats['skipped'] += 1
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
                start_date=parse_date(data.get('start_date')),
                salary=to_decimal(data.get('salary')),
                branch=get_or_create_branch(data.get('branch')),
                department_filter=data.get('department_filter'),
                cost_center=get_or_create_cost_center(data.get('cost_center')),
                notes=data.get('notes'),
                file_path=data.get('file_path') or '',
                file_name=data.get('file_name') or data.get('original_filename'),
                status=clean_status(data.get('status'), RequestStatus) or RequestStatus.PENDING,
                branch_manager_approval=clean_status(data.get('branch_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                department_manager_approval=clean_status(data.get('department_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                manager_approval=clean_status(data.get('manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                approval_notes=data.get('approval_notes'),
                uploaded_by_id=get_user_id(data.get('uploaded_by')) or admin_user.id,
                assigned_to_id=get_user_id(data.get('assigned_to')),
                completed_by_id=get_user_id(data.get('completed_by')),
                branch_approved_by_id=get_user_id(data.get('branch_approved_by')),
                department_approved_by_id=get_user_id(data.get('department_approved_by')),
                manager_approved_by_id=get_user_id(data.get('manager_approved_by')),
                assigned_employee_number=data.get('assigned_employee_number'),
            )
            obj.save()
            
            created_at = parse_datetime(data.get('created_at'))
            if created_at:
                EmployeeFile.objects.filter(pk=record_id).update(created_at=created_at)
            
            stats['imported'] += 1
        except Exception as e:
            stats['errors'] += 1
            if stats['errors'] <= 3:
                print(f"   Error ID {data.get('id')}: {e}")
    
    print(f"   [OK] {stats['imported']} | SKIP  {stats['skipped']} | ERR {stats['errors']}")


def import_advances(content: str):
    """استيراد السلف"""
    print("\n[ADVANCES] استيراد السلف...")
    reset_stats()
    
    cols = extract_columns(content, 'advance_files')
    if not cols:
        print("   No data found")
        return
    
    for row_str in extract_rows(content, 'advance_files'):
        try:
            values = parse_row_values(row_str)
            values += [None] * (len(cols) - len(values))
            data = dict(zip(cols, values))
            
            record_id = data['id']
            if AdvanceFile.objects.filter(pk=record_id).exists():
                stats['skipped'] += 1
                continue
            
            obj = AdvanceFile(
                id=record_id,
                employee_name=str(data['employee_name'] or ''),
                employee_number=str(data.get('employee_number') or '') or None,
                advance_amount=to_decimal(data.get('advance_amount')),
                advance_date=parse_date(data.get('advance_date')),
                file_path=data.get('file_path') or '',
                file_name=data.get('file_name') or data.get('original_filename'),
                notes=data.get('notes'),
                status=clean_status(data.get('status'), RequestStatus) or RequestStatus.PENDING,
                branch=get_or_create_branch(data.get('branch')),
                department_filter=data.get('department_filter'),
                installments=to_int(data.get('installments')) or 1,
                branch_manager_approval=clean_status(data.get('branch_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                department_manager_approval=clean_status(data.get('department_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                manager_approval=clean_status(data.get('manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                approval_notes=data.get('approval_notes'),
                uploaded_by_id=get_user_id(data.get('uploaded_by')) or admin_user.id,
                assigned_to_id=get_user_id(data.get('assigned_to')),
                completed_by_id=get_user_id(data.get('completed_by')),
                branch_approved_by_id=get_user_id(data.get('branch_approved_by')),
                department_approved_by_id=get_user_id(data.get('department_approved_by')),
                manager_approved_by_id=get_user_id(data.get('manager_approved_by')),
            )
            obj.save()
            
            created_at = parse_datetime(data.get('created_at'))
            if created_at:
                AdvanceFile.objects.filter(pk=record_id).update(created_at=created_at)
            
            stats['imported'] += 1
        except Exception as e:
            stats['errors'] += 1
    
    print(f"   [OK] {stats['imported']} | SKIP  {stats['skipped']} | ERR {stats['errors']}")


def import_statements(content: str):
    """استيراد البيانات والإجازات"""
    print("\n📋 استيراد البيانات والإجازات...")
    reset_stats()
    
    # استخراج الأعمدة من SQL
    cols = extract_columns(content, 'statement_files')
    if not cols:
        print("   [VIOLATIONS] لا يوجد بيانات")
        return
    
    for row_str in extract_rows(content, 'statement_files'):
        try:
            values = parse_row_values(row_str)
            values += [None] * (len(cols) - len(values))
            data = dict(zip(cols, values))
            
            record_id = data['id']
            if StatementFile.objects.filter(pk=record_id).exists():
                stats['skipped'] += 1
                continue
            
            obj = StatementFile(
                id=record_id,
                employee_name=str(data['employee_name'] or ''),
                employee_number=str(data.get('employee_number') or '') or None,
                statement_type=str(data.get('statement_type') or ''),
                file_path=data.get('file_path') or '',
                file_name=data.get('file_name') or data.get('original_filename'),
                notes=data.get('notes'),
                status=clean_status(data.get('status'), RequestStatus) or RequestStatus.PENDING,
                branch=get_or_create_branch(data.get('branch')),
                department_filter=data.get('department_filter'),
                vacation_days=to_int(data.get('vacation_days')),
                vacation_start=parse_date(data.get('vacation_start')),
                vacation_end=parse_date(data.get('vacation_end')),
                vacation_balance=to_decimal(data.get('vacation_balance')),
                branch_manager_approval=clean_status(data.get('branch_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                department_manager_approval=clean_status(data.get('department_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                manager_approval=clean_status(data.get('manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                approval_notes=data.get('approval_notes'),
                uploaded_by_id=get_user_id(data.get('uploaded_by')) or admin_user.id,
                assigned_to_id=get_user_id(data.get('assigned_to')),
                completed_by_id=get_user_id(data.get('completed_by')),
                branch_approved_by_id=get_user_id(data.get('branch_approved_by')),
                department_approved_by_id=get_user_id(data.get('department_approved_by')),
                manager_approved_by_id=get_user_id(data.get('manager_approved_by')),
            )
            obj.save()
            
            created_at = parse_datetime(data.get('created_at'))
            if created_at:
                StatementFile.objects.filter(pk=record_id).update(created_at=created_at)
            
            stats['imported'] += 1
        except Exception as e:
            stats['errors'] += 1
            if stats['errors'] == 1:
                print(f"   First error: {e}")
    
    print(f"   [OK] {stats['imported']} | SKIP  {stats['skipped']} | ERR {stats['errors']}")


def import_violations(content: str):
    """استيراد المخالفات"""
    print("\n[VIOLATIONS] استيراد المخالفات...")
    reset_stats()
    
    cols = extract_columns(content, 'violation_files')
    if not cols:
        print("   No data found")
        return
    
    for row_str in extract_rows(content, 'violation_files'):
        try:
            values = parse_row_values(row_str)
            values += [None] * (len(cols) - len(values))
            data = dict(zip(cols, values))
            
            record_id = data['id']
            if ViolationFile.objects.filter(pk=record_id).exists():
                stats['skipped'] += 1
                continue
            
            obj = ViolationFile(
                id=record_id,
                employee_name=str(data['employee_name'] or ''),
                employee_number=str(data.get('employee_number') or '') or None,
                violation_type=str(data.get('violation_type') or ''),
                violation_date=parse_date(data.get('violation_date')),
                file_path=data.get('file_path') or '',
                violation_notes=data.get('violation_notes'),
                employee_statement=data.get('employee_statement'),
                status=clean_status(data.get('status'), RequestStatus) or RequestStatus.PENDING,
                branch=get_or_create_branch(data.get('branch')),
                employee_branch=get_or_create_branch(data.get('employee_branch')),
                employee_department=data.get('employee_department'),
                department_filter=data.get('department_filter'),
                branch_manager_approval=clean_status(data.get('branch_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                department_manager_approval=clean_status(data.get('department_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                manager_approval=clean_status(data.get('manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                approval_notes=data.get('approval_notes'),
                uploaded_by_id=get_user_id(data.get('uploaded_by')) or admin_user.id,
                assigned_to_id=get_user_id(data.get('assigned_to')),
                branch_approved_by_id=get_user_id(data.get('branch_approved_by')),
                department_approved_by_id=get_user_id(data.get('department_approved_by')),
                manager_approved_by_id=get_user_id(data.get('manager_approved_by')),
            )
            obj.save()
            
            created_at = parse_datetime(data.get('uploaded_at'))
            if created_at:
                ViolationFile.objects.filter(pk=record_id).update(created_at=created_at)
            
            stats['imported'] += 1
        except Exception as e:
            stats['errors'] += 1
            if stats['errors'] == 1:
                print(f"   First error: {e}")
    
    print(f"   [OK] {stats['imported']} | SKIP  {stats['skipped']} | ERR {stats['errors']}")


def import_terminations(content: str):
    """استيراد إنهاء الخدمات"""
    print("\n[TERMINATIONS] استيراد إنهاء الخدمات...")
    reset_stats()
    
    cols = extract_columns(content, 'termination_files')
    if not cols:
        print("   No data found")
        return
    
    for row_str in extract_rows(content, 'termination_files'):
        try:
            values = parse_row_values(row_str)
            values += [None] * (len(cols) - len(values))
            data = dict(zip(cols, values))
            
            record_id = data['id']
            if TerminationFile.objects.filter(pk=record_id).exists():
                stats['skipped'] += 1
                continue
            
            obj = TerminationFile(
                id=record_id,
                employee_name=str(data['employee_name'] or ''),
                employee_number=str(data.get('employee_number') or '') or None,
                national_id=str(data.get('national_id') or '') or None,
                nationality=str(data.get('nationality') or '') or None,
                notes=data.get('notes'),
                file_path=data.get('file_path') or '',
                status=clean_status(data.get('status'), RequestStatus) or RequestStatus.PENDING,
                branch=get_or_create_branch(data.get('branch')),
                department_filter=data.get('department_filter'),
                branch_manager_approval=clean_status(data.get('branch_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                department_manager_approval=clean_status(data.get('department_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                manager_approval=clean_status(data.get('manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                approval_notes=data.get('approval_notes'),
                uploaded_by_id=get_user_id(data.get('uploaded_by')) or admin_user.id,
                assigned_to_id=get_user_id(data.get('assigned_to')),
                branch_approved_by_id=get_user_id(data.get('branch_approved_by')),
                department_approved_by_id=get_user_id(data.get('department_approved_by')),
                manager_approved_by_id=get_user_id(data.get('manager_approved_by')),
            )
            obj.save()
            
            created_at = parse_datetime(data.get('created_at'))
            if created_at:
                TerminationFile.objects.filter(pk=record_id).update(created_at=created_at)
            
            stats['imported'] += 1
        except Exception as e:
            stats['errors'] += 1
    
    print(f"   [OK] {stats['imported']} | SKIP  {stats['skipped']} | ERR {stats['errors']}")


def import_medical_insurance(content: str):
    """استيراد التأمين الطبي"""
    print("\n[MEDICAL] استيراد التأمين الطبي...")
    reset_stats()
    
    cols = extract_columns(content, 'medical_insurance')
    if not cols:
        print("   No data found")
        return
    
    for row_str in extract_rows(content, 'medical_insurance'):
        try:
            values = parse_row_values(row_str)
            values += [None] * (len(cols) - len(values))
            data = dict(zip(cols, values))
            
            record_id = data['id']
            if MedicalInsurance.objects.filter(pk=record_id).exists():
                stats['skipped'] += 1
                continue
            
            obj = MedicalInsurance(
                id=record_id,
                employee_name=str(data['employee_name'] or ''),
                insurance_type=str(data.get('insurance_type') or ''),
                details=str(data.get('details') or ''),
                file_path=data.get('file_path') or '',
                status=clean_status(data.get('status'), RequestStatus) or RequestStatus.PENDING,
                branch=get_or_create_branch(data.get('branch')),
                department_filter=data.get('department_filter'),
                branch_manager_approval=clean_status(data.get('branch_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                department_manager_approval=clean_status(data.get('department_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                manager_approval=clean_status(data.get('manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                approval_notes=data.get('approval_notes'),
                uploaded_by_id=get_user_id(data.get('uploaded_by')) or admin_user.id,
                assigned_to_id=get_user_id(data.get('assigned_to')),
                branch_approved_by_id=get_user_id(data.get('branch_approved_by')),
                department_approved_by_id=get_user_id(data.get('department_approved_by')),
                manager_approved_by_id=get_user_id(data.get('manager_approved_by')),
            )
            obj.save()
            
            created_at = parse_datetime(data.get('uploaded_at'))
            if created_at:
                MedicalInsurance.objects.filter(pk=record_id).update(created_at=created_at)
            
            stats['imported'] += 1
        except Exception as e:
            stats['errors'] += 1
            if stats['errors'] == 1:
                print(f"   First error: {e}")
    
    print(f"   [OK] {stats['imported']} | SKIP  {stats['skipped']} | ERR {stats['errors']}")


def import_medical_excuses(content: str):
    """استيراد الأعذار الطبية"""
    print("\n[EXCUSES] استيراد الأعذار الطبية...")
    reset_stats()
    
    cols = extract_columns(content, 'medical_excuses')
    if not cols:
        print("   No data found")
        return
    
    for row_str in extract_rows(content, 'medical_excuses'):
        try:
            values = parse_row_values(row_str)
            values += [None] * (len(cols) - len(values))
            data = dict(zip(cols, values))
            
            record_id = data['id']
            if MedicalExcuse.objects.filter(pk=record_id).exists():
                stats['skipped'] += 1
                continue
            
            obj = MedicalExcuse(
                id=record_id,
                employee_name=str(data['employee_name'] or ''),
                employee_id_number=str(data.get('employee_id') or ''),
                branch=str(data.get('branch') or ''),
                department=str(data.get('department') or ''),
                cost_center=get_or_create_cost_center(data.get('cost_center')),
                excuse_reason=str(data.get('excuse_reason') or ''),
                excuse_date=parse_date(data.get('excuse_date')),
                excuse_duration=to_int(data.get('excuse_duration')) or 1,
                file_path=data.get('file_path') or '',
                status=clean_status(data.get('status'), RequestStatus) or RequestStatus.PENDING,
                department_filter=data.get('department_filter'),
                branch_manager_approval=clean_status(data.get('branch_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                department_manager_approval=clean_status(data.get('department_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                manager_approval=clean_status(data.get('manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                approval_notes=data.get('approval_notes'),
                uploaded_by_id=get_user_id(data.get('uploaded_by')) or admin_user.id,
                assigned_to_id=get_user_id(data.get('assigned_to')),
                branch_approved_by_id=get_user_id(data.get('branch_approved_by')),
                department_approved_by_id=get_user_id(data.get('department_approved_by')),
                manager_approved_by_id=get_user_id(data.get('manager_approved_by')),
            )
            obj.save()
            
            created_at = parse_datetime(data.get('created_at'))
            if created_at:
                MedicalExcuse.objects.filter(pk=record_id).update(created_at=created_at)
            
            stats['imported'] += 1
        except Exception as e:
            stats['errors'] += 1
            if stats['errors'] == 1:
                print(f"   First error: {e}")
    
    print(f"   [OK] {stats['imported']} | SKIP  {stats['skipped']} | ERR {stats['errors']}")


def import_salary_adjustments(content: str):
    """استيراد تعديلات الرواتب"""
    print("\n[SALARY] استيراد تعديلات الرواتب...")
    reset_stats()
    
    cols = extract_columns(content, 'salary_adjustments')
    if not cols:
        print("   No data found")
        return
    
    for row_str in extract_rows(content, 'salary_adjustments'):
        try:
            values = parse_row_values(row_str)
            values += [None] * (len(cols) - len(values))
            data = dict(zip(cols, values))
            
            record_id = data['id']
            if SalaryAdjustment.objects.filter(pk=record_id).exists():
                stats['skipped'] += 1
                continue
            
            obj = SalaryAdjustment(
                id=record_id,
                employee_name=str(data['employee_name'] or ''),
                employee_number=str(data.get('employee_number') or ''),
                department=str(data.get('department') or ''),
                current_salary=to_decimal(data.get('current_salary')) or Decimal('0'),
                salary_increase=to_decimal(data.get('salary_increase')) or Decimal('0'),
                new_salary=to_decimal(data.get('new_salary')) or Decimal('0'),
                adjustment_reason=data.get('adjustment_reason'),
                notes=data.get('notes'),
                status=clean_status(data.get('status'), RequestStatus) or RequestStatus.PENDING,
                branch=get_or_create_branch(data.get('branch')),
                cost_center=get_or_create_cost_center(data.get('cost_center')),
                department_filter=data.get('department_filter'),
                branch_manager_approval=clean_status(data.get('branch_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                department_manager_approval=clean_status(data.get('department_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                manager_approval=clean_status(data.get('manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                approval_notes=data.get('approval_notes'),
                uploaded_by_id=get_user_id(data.get('uploaded_by')) or admin_user.id,
                assigned_to_id=get_user_id(data.get('assigned_to')),
                branch_approved_by_id=get_user_id(data.get('branch_approved_by')),
                department_approved_by_id=get_user_id(data.get('department_approved_by')),
                manager_approved_by_id=get_user_id(data.get('manager_approved_by')),
            )
            obj.save()
            
            created_at = parse_datetime(data.get('created_at'))
            if created_at:
                SalaryAdjustment.objects.filter(pk=record_id).update(created_at=created_at)
            
            stats['imported'] += 1
        except Exception as e:
            stats['errors'] += 1
            if stats['errors'] == 1:
                print(f"   First error: {e}")
    
    print(f"   [OK] {stats['imported']} | SKIP  {stats['skipped']} | ERR {stats['errors']}")


def import_transfers(content: str):
    """استيراد طلبات النقل"""
    print("\n[TRANSFERS] استيراد طلبات النقل...")
    reset_stats()
    
    cols = extract_columns(content, 'employee_transfer_requests')
    if not cols:
        print("   No data found")
        return
    
    for row_str in extract_rows(content, 'employee_transfer_requests'):
        try:
            values = parse_row_values(row_str)
            values += [None] * (len(cols) - len(values))
            data = dict(zip(cols, values))
            
            record_id = data['id']
            if EmployeeTransferRequest.objects.filter(pk=record_id).exists():
                stats['skipped'] += 1
                continue
            
            obj = EmployeeTransferRequest(
                id=record_id,
                employee_name=str(data['employee_name'] or ''),
                employee_id_number=str(data.get('employee_id') or ''),
                current_branch=get_or_create_branch(data.get('current_branch')),
                requested_branch=get_or_create_branch(data.get('requested_branch')),
                current_department=str(data.get('current_department') or ''),
                requested_department=str(data.get('requested_department') or ''),
                department_filter=data.get('department_filter'),
                current_cost_center=get_or_create_cost_center(data.get('current_cost_center')),
                new_cost_center=get_or_create_cost_center(data.get('new_cost_center')),
                transfer_reason=str(data.get('transfer_reason') or ''),
                preferred_date=parse_date(data.get('preferred_date')),
                status=clean_status(data.get('status'), RequestStatus) or RequestStatus.PENDING,
                assign_note=data.get('assign_note'),
                in_progress_at=parse_datetime(data.get('in_progress_at')),
                completed_at=parse_datetime(data.get('completed_at')),
                branch_manager_approval=clean_status(data.get('branch_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                department_manager_approval=clean_status(data.get('department_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                manager_approval=clean_status(data.get('manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                approval_notes=data.get('approval_notes'),
                uploaded_by_id=get_user_id(data.get('uploaded_by')) or admin_user.id,
                assigned_to_id=get_user_id(data.get('assigned_to')),
                completed_by_id=get_user_id(data.get('completed_by')),
                branch_approved_by_id=get_user_id(data.get('branch_approved_by')),
                department_approved_by_id=get_user_id(data.get('department_approved_by')),
                manager_approved_by_id=get_user_id(data.get('manager_approved_by')),
            )
            obj.save()
            
            created_at = parse_datetime(data.get('created_at'))
            if created_at:
                EmployeeTransferRequest.objects.filter(pk=record_id).update(created_at=created_at)
            
            stats['imported'] += 1
        except Exception as e:
            stats['errors'] += 1
            if stats['errors'] == 1:
                print(f"   First error: {e}")
    
    print(f"   [OK] {stats['imported']} | SKIP  {stats['skipped']} | ERR {stats['errors']}")


def import_attendance(content: str):
    """استيراد سجلات الحضور"""
    print("\n[ATTENDANCE] استيراد سجلات الحضور...")
    reset_stats()
    
    cols = extract_columns(content, 'attendance_records')
    if not cols:
        print("   No data found")
        return
    
    for row_str in extract_rows(content, 'attendance_records'):
        try:
            values = parse_row_values(row_str)
            values += [None] * (len(cols) - len(values))
            data = dict(zip(cols, values))
            
            record_id = data['id']
            if AttendanceRecord.objects.filter(pk=record_id).exists():
                stats['skipped'] += 1
                continue
            
            obj = AttendanceRecord(
                id=record_id,
                batch_id=str(data.get('batch_id') or ''),
                batch_date=parse_date(data.get('batch_date')),
                employee_name=str(data['employee_name'] or ''),
                title=data.get('title'),
                branch=get_or_create_branch(data.get('branch')),
                department_filter=data.get('department_filter'),
                date_from=parse_date(data.get('date_from')),
                nationality=data.get('nationality'),
                shift_start=data.get('shift_start'),
                shift_end=data.get('shift_end'),
                attendance_date=parse_date(data.get('attendance_date')),
                notes=data.get('notes'),
                status=clean_status(data.get('status'), RequestStatus) or RequestStatus.PENDING,
                branch_manager_approval=clean_status(data.get('branch_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                department_manager_approval=clean_status(data.get('department_manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                manager_approval=clean_status(data.get('manager_approval'), ApprovalStatus) or ApprovalStatus.PENDING,
                approval_notes=data.get('approval_notes'),
                uploaded_by_id=get_user_id(data.get('uploaded_by')) or admin_user.id,
                assigned_to_id=get_user_id(data.get('assigned_to')),
            )
            obj.save()
            
            created_at = parse_datetime(data.get('created_at'))
            if created_at:
                AttendanceRecord.objects.filter(pk=record_id).update(created_at=created_at)
            
            stats['imported'] += 1
        except Exception as e:
            stats['errors'] += 1
            if stats['errors'] == 1:
                print(f"   First error: {e}")
    
    print(f"   [OK] {stats['imported']} | SKIP  {stats['skipped']} | ERR {stats['errors']}")


def import_messages(content: str):
    """استيراد الرسائل"""
    print("\n[MESSAGES] استيراد الرسائل...")
    reset_stats()
    
    cols = extract_columns(content, 'messages')
    if not cols:
        print("   No data found")
        return
    
    for row_str in extract_rows(content, 'messages'):
        try:
            values = parse_row_values(row_str)
            values += [None] * (len(cols) - len(values))
            data = dict(zip(cols, values))
            
            record_id = data['id']
            if UserMessage.objects.filter(pk=record_id).exists():
                stats['skipped'] += 1
                continue
            
            sender = get_user(data.get('sender_id'))
            receiver = get_user(data.get('receiver_id'))
            reply_by = get_user(data.get('reply_by'))
            
            if not sender or not receiver:
                stats['errors'] += 1
                continue
            
            obj = UserMessage(
                id=record_id,
                sender=sender,
                receiver=receiver,
                message_text=str(data.get('message_text') or '').replace('\r\n', '\n'),
                status=data.get('status') or 'open',
                reply_text=data.get('reply_text'),
                reply_by=reply_by,
                reply_at=parse_datetime(data.get('reply_at')),
                reply_file_path=data.get('reply_file_path'),
            )
            obj.save()
            
            sent_at = parse_datetime(data.get('sent_at'))
            if sent_at:
                UserMessage.objects.filter(pk=record_id).update(sent_at=sent_at)
            
            stats['imported'] += 1
        except Exception as e:
            stats['errors'] += 1
    
    print(f"   [OK] {stats['imported']} | SKIP  {stats['skipped']} | ERR {stats['errors']}")


# ==============================
# التنفيذ الرئيسي
# ==============================

def main():
    global admin_user
    
    print("=" * 60)
    print("         استيراد شامل لبيانات HR Pro")
    print("=" * 60)
    
    # التحقق من ملف SQL
    if not SQL_FILE.exists():
        print(f"ERR ملف SQL غير موجود: {SQL_FILE}")
        sys.exit(1)
    
    # جلب مستخدم admin
    admin_user = User.objects.filter(is_superuser=True).first() or User.objects.first()
    if not admin_user:
        print("ERR لا يوجد مستخدمين في النظام!")
        sys.exit(1)
    print(f"[USER] المستخدم الافتراضي: {admin_user}")
    
    # مسح البيانات القديمة إذا تم تمرير --clean
    if '--clean' in sys.argv:
        print("\n[CLEAN] مسح البيانات القديمة...")
        UserMessage.objects.all().delete()
        print("   - الرسائل")
        AttendanceRecord.objects.all().delete()
        print("   - سجلات الحضور")
        EmployeeTransferRequest.objects.all().delete()
        print("   - طلبات النقل")
        SalaryAdjustment.objects.all().delete()
        print("   - تعديلات الرواتب")
        MedicalExcuse.objects.all().delete()
        print("   - الأعذار الطبية")
        MedicalInsurance.objects.all().delete()
        print("   - التأمين الطبي")
        TerminationFile.objects.all().delete()
        print("   - إنهاء الخدمات")
        ViolationFile.objects.all().delete()
        print("   - المخالفات")
        StatementFile.objects.all().delete()
        print("   - البيانات/الإجازات")
        AdvanceFile.objects.all().delete()
        print("   - السلف")
        EmployeeFile.objects.all().delete()
        print("   - الموظفين")
        Branch.objects.all().delete()
        print("   - الفروع")
        CostCenter.objects.all().delete()
        print("   - مراكز التكلفة")
        Organization.objects.all().delete()
        print("   - المؤسسات")
        Sponsorship.objects.all().delete()
        print("   - الكفالات")
        print("   [OK] تم مسح جميع البيانات!")
    
    # قراءة ملف SQL
    print(f"\n[FILE] قراءة ملف SQL: {SQL_FILE.name}")
    with open(SQL_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    print(f"   حجم الملف: {len(content):,} حرف")
    
    # استيراد البيانات الأساسية
    import_branches(content)
    import_cost_centers(content)
    import_organizations(content)
    import_sponsorships(content)
    
    # استيراد الطلبات والشاشات
    import_employees(content)
    import_advances(content)
    import_statements(content)
    import_violations(content)
    import_terminations(content)
    import_medical_insurance(content)
    import_medical_excuses(content)
    import_salary_adjustments(content)
    import_transfers(content)
    import_attendance(content)
    import_messages(content)
    
    # ملخص نهائي
    print("\n" + "=" * 60)
    print("📊 ملخص البيانات:")
    print("=" * 60)
    print(f"   📍 الفروع: {Branch.objects.count()}")
    print(f"   📍 مراكز التكلفة: {CostCenter.objects.count()}")
    print(f"   📍 المؤسسات: {Organization.objects.count()}")
    print(f"   📍 الكفالات: {Sponsorship.objects.count()}")
    print(f"   👥 الموظفين: {EmployeeFile.objects.count()}")
    print(f"   💰 السلف: {AdvanceFile.objects.count()}")
    print(f"   📋 البيانات/الإجازات: {StatementFile.objects.count()}")
    print(f"   [VIOLATIONS]  المخالفات: {ViolationFile.objects.count()}")
    print(f"   🚪 إنهاء الخدمات: {TerminationFile.objects.count()}")
    print(f"   🏥 التأمين الطبي: {MedicalInsurance.objects.count()}")
    print(f"   🩺 الأعذار الطبية: {MedicalExcuse.objects.count()}")
    print(f"   💵 تعديلات الرواتب: {SalaryAdjustment.objects.count()}")
    print(f"   🔄 طلبات النقل: {EmployeeTransferRequest.objects.count()}")
    print(f"   📅 سجلات الحضور: {AttendanceRecord.objects.count()}")
    print(f"   [MESSAGES]  الرسائل: {UserMessage.objects.count()}")
    print("=" * 60)
    print("[OK] اكتمل الاستيراد بنجاح!")


if __name__ == '__main__':
    main()
