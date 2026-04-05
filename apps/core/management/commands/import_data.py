"""
Management Command: import_data
================================
استيراد البيانات من ملف قاعدة البيانات SQL
يتم قراءة الملف وتحليل البيانات وإدراجها في Django Models
"""

import re
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError


class SQLParser:
    """فئة لتحليل بيانات SQL"""
    
    @staticmethod
    def parse_insert_values(sql_line):
        """
        تحليل سطر INSERT VALUES
        مثال: INSERT INTO `table` (...) VALUES (val1, 'val2', NULL, ...)
        """
        # البحث عن قسم VALUES
        match = re.search(r'VALUES\s*\((.*)\)', sql_line, re.DOTALL | re.IGNORECASE)
        if not match:
            return None
        
        values_str = match.group(1)
        values = []
        
        # تحليل القيم مع معالجة الفواصل والنصوص
        current_value = ""
        in_string = False
        string_char = None
        
        for char in values_str:
            if char in ('"', "'") and (not in_string or string_char == char):
                if in_string and string_char == char:
                    in_string = False
                elif not in_string:
                    in_string = True
                    string_char = char
                current_value += char
            elif char == ',' and not in_string:
                values.append(current_value.strip())
                current_value = ""
            else:
                current_value += char
        
        if current_value.strip():
            values.append(current_value.strip())
        
        return values
    
    @staticmethod
    def parse_value(value_str):
        """تحويل قيمة SQL إلى قيمة Python"""
        value_str = value_str.strip()
        
        if value_str.upper() == 'NULL':
            return None
        elif value_str.upper() in ('TRUE', '1'):
            return True
        elif value_str.upper() in ('FALSE', '0'):
            return False
        elif value_str.startswith("'") and value_str.endswith("'"):
            # نص مقتبس
            return value_str[1:-1].replace("\\'", "'").replace('\\"', '"')
        elif value_str.startswith('"') and value_str.endswith('"'):
            # نص مع علامات الاقتباس المزدوجة
            return value_str[1:-1].replace('\\"', '"')
        else:
            # محاولة تحويل إلى رقم
            try:
                if '.' in value_str:
                    return Decimal(value_str)
                else:
                    return int(value_str)
            except ValueError:
                return value_str


class Command(BaseCommand):
    """أمر Django لاستيراد البيانات من ملف SQL"""
    
    help = 'استيراد البيانات من ملف قاعدة البيانات SQL إلى Django'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            required=True,
            help='مسار ملف SQL'
        )
        parser.add_argument(
            '--table',
            type=str,
            default=None,
            help='اسم الجدول المراد استيراده (اختياري)'
        )
    
    def handle(self, *args, **options):
        file_path = options.get('file')
        table_name = options.get('table')
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()
        except FileNotFoundError:
            raise CommandError(f'الملف غير موجود: {file_path}')
        except Exception as e:
            raise CommandError(f'خطأ في قراءة الملف: {str(e)}')
        
        self.stdout.write('جاري تحليل ملف SQL...')
        
        # استخراج جميع عمليات INSERT
        insert_matches = re.finditer(
            r'INSERT INTO\s+`([^`]+)`\s*\(([^)]+)\)\s*VALUES\s*(.+?)(?=;)',
            sql_content,
            re.DOTALL | re.IGNORECASE
        )
        
        total_imported = 0
        
        for match in insert_matches:
            table = match.group(1)
            values_str = match.group(3)
            
            # تصفية الجداول إن كانت محددة
            if table_name and table != table_name:
                continue
            
            value_rows = self._parse_value_rows(values_str)
            
            # Import handlers not yet implemented
            self.stdout.write(f'Skipped table: {table} ({len(value_rows)} rows)')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✓ اكتمل الاستيراد! تم استيراد {total_imported} سجل إجمالي'
            )
        )
    
    def _parse_value_rows(self, values_str):
        """تحليل جميع صفوف VALUES"""
        rows = []
        # فصل الصفوف المختلفة
        # هذا تقريب - قد يحتاج إلى تحسين
        row_pattern = r'\(([^)]+)\)(?=\s*,\s*\(|\s*$)'
        matches = re.finditer(row_pattern, values_str, re.DOTALL)
        
        parser = SQLParser()
        for match in matches:
            row_values_str = match.group(1)
            # تحليل القيم في الصف
            values = parser.parse_insert_values(f'({row_values_str})')
            if values:
                parsed_values = [parser.parse_value(v) for v in values]
                rows.append(parsed_values)
        
        return rows
    
    def _import_table(self, *args):
        # All import handlers are not yet implemented
        return 0

    def _get_column_index(self, columns, column_name):
        try:
            return columns.index(column_name)
        except ValueError:
            return None
