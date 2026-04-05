"""
نماذج نظام الموارد البشرية - HR Pro Models
============================================
يحتوي على جميع الجداول المطابقة لقاعدة بيانات MySQL الأصلية
مع العلاقات (ForeignKey, ManyToMany) وحقول البيانات
"""

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import (
    MinValueValidator,
    MaxValueValidator,
    FileExtensionValidator,
)
from django.utils import timezone
from django.conf import settings
from decimal import Decimal


# ==============================
# الثوابت والخيارات / Choices
# ==============================

class ApprovalStatus(models.TextChoices):
    """حالات الاعتماد لجميع الطلبات"""
    PENDING = 'pending', 'معلّق'
    APPROVED = 'approved', 'معتمد'
    REJECTED = 'rejected', 'مرفوض'


class RequestStatus(models.TextChoices):
    """حالات الطلبات العامة"""
    PENDING = 'pending', 'معلّق'
    IN_PROGRESS = 'in_progress', 'قيد المعالجة'
    COMPLETED = 'completed', 'مكتمل'
    APPROVED = 'approved', 'معتمد'
    REJECTED = 'rejected', 'مرفوض'


class UserRole(models.TextChoices):
    """أدوار المستخدمين في النظام - متوافق مع المجموعات"""
    BRANCH_EMPLOYEE = 'branch_employee', 'موظف فرع'
    BRANCH_MANAGER = 'branch_manager', 'مدير فرع'
    HR_MANAGER = 'hr_manager', 'مدير الموارد'
    ADMIN = 'admin', 'مدير الأدمن'


class Department(models.TextChoices):
    """الإدارات المتاحة"""
    PURCHASING = 'purchasing', 'إدارة المشتريات'
    FINANCIAL = 'financial', 'إدارة المالية'
    TECHNICAL = 'technical', 'إدارة التقنية'
    DATA = 'data', 'إدارة البيانات'


class MessageType(models.TextChoices):
    """أنواع الرسائل"""
    INFO = 'info', 'معلومات'
    WARNING = 'warning', 'تحذير'
    SUCCESS = 'success', 'نجاح'
    DANGER = 'danger', 'خطر'


class StartType(models.TextChoices):
    """نوع بداية الموظف"""
    NEW = 'new', 'جديد'
    REPLACEMENT = 'replacement', 'بديل'
    RETURN = 'return', 'عائد'


class ActivityAction(models.TextChoices):
    """أنواع العمليات المسجلة"""
    CREATE = 'create', 'إنشاء'
    UPDATE = 'update', 'تعديل'
    DELETE = 'delete', 'حذف'
    VIEW = 'view', 'عرض'
    LOGIN = 'login', 'تسجيل دخول'
    LOGOUT = 'logout', 'تسجيل خروج'
    UPLOAD = 'upload', 'رفع ملف'
    DOWNLOAD = 'download', 'تحميل'
    APPROVE = 'approve', 'اعتماد'
    REJECT = 'reject', 'رفض'
    EXPORT = 'export', 'تصدير'
    IMPORT = 'import_data', 'استيراد'


# ==============================
# دالة مساعدة لمسارات رفع الملفات
# ==============================

import uuid
import os

def upload_to(instance, filename):
    """
    تحديد مسار رفع الملفات بناءً على نوع النموذج.
    يعالج نماذج Proxy بصواب بالرجوع إلى النموذج الأصلي (concrete model).
    يُنظّف اسم الملف ليكون آمناً للتخزين السحابي.
    """
    # استخدام النموذج الأصلي وليس الـ proxy لضمان مسار موحد
    cls = instance.__class__
    concrete = cls._meta.proxy_for_model or cls
    model_name = concrete.__name__.lower()
    
    # الحصول على امتداد الملف
    ext = os.path.splitext(filename)[1].lower()
    
    # إنشاء اسم ملف فريد وآمن (بدون أحرف عربية)
    safe_filename = f'{uuid.uuid4().hex}{ext}'
    
    return f'uploads/{model_name}/{timezone.now().strftime("%Y/%m")}/{safe_filename}'


# ==============================
# نموذج المستخدم المخصص / Custom User Model
# ==============================

class User(AbstractUser):
    """
    نموذج المستخدم المخصص - يطابق جدول users في PHP
    يدعم الأدوار المتعددة والفروع والإدارات
    """
    phone = models.CharField(
        max_length=20, blank=True, null=True,
        verbose_name='رقم الهاتف'
    )
    department = models.CharField(
        max_length=100, blank=True, null=True,
        choices=Department.choices,
        verbose_name='الإدارة'
    )
    branch = models.ForeignKey(
        'Branch', to_field='name', db_column='branch',
        on_delete=models.SET_NULL, null=True, blank=True,
        db_constraint=False, verbose_name='الفرع'
    )
    role = models.CharField(
        max_length=50, choices=UserRole.choices,
        default=UserRole.BRANCH_EMPLOYEE,
        verbose_name='الدور'
    )

    class Meta:
        verbose_name = 'مستخدم'
        verbose_name_plural = 'المستخدمون'
        ordering = ['-date_joined']

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    @property
    def is_admin_role(self):
        """هل المستخدم مدير أدمن؟"""
        return self.role == UserRole.ADMIN

    @property
    def is_manager_role(self):
        """هل المستخدم مدير موارد أو أعلى؟"""
        return self.role in (UserRole.ADMIN, UserRole.HR_MANAGER)

    @property
    def is_branch_manager_role(self):
        """هل المستخدم مدير فرع؟"""
        return self.role == UserRole.BRANCH_MANAGER


# ==============================
# نموذج قاعدي مشترك لجميع الطلبات
# ==============================

class BaseRequest(models.Model):
    """
    نموذج قاعدي مجرد يحتوي على الحقول المشتركة
    بين جميع أنواع الطلبات (الاعتمادات، الحالة، التعيين...)
    """
    # حالة الطلب
    status = models.CharField(
        max_length=20, choices=RequestStatus.choices,
        default=RequestStatus.PENDING,
        verbose_name='الحالة', db_index=True
    )

    # سلسلة الاعتمادات الثلاثية
    branch_manager_approval = models.CharField(
        max_length=20, choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
        verbose_name='اعتماد مدير الفرع', db_index=True
    )
    department_manager_approval = models.CharField(
        max_length=20, choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
        verbose_name='اعتماد مدير الإدارة', db_index=True
    )
    manager_approval = models.CharField(
        max_length=20, choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
        verbose_name='اعتماد المدير العام', db_index=True
    )

    # المعتمدون
    branch_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='%(class)s_branch_approvals',
        verbose_name='معتمد من مدير الفرع'
    )
    department_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='%(class)s_dept_approvals',
        verbose_name='معتمد من مدير الإدارة'
    )
    manager_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='%(class)s_mgr_approvals',
        verbose_name='معتمد من المدير العام'
    )

    approval_notes = models.TextField(
        blank=True, null=True,
        verbose_name='ملاحظات الاعتماد'
    )

    # التعيين والتكليف
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='%(class)s_uploads',
        verbose_name='رُفع بواسطة'
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='%(class)s_assignments',
        verbose_name='معيّن إلى'
    )
    assign_note = models.TextField(
        blank=True, null=True,
        verbose_name='ملاحظة التكليف'
    )

    # الإنجاز
    in_progress_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='وقت بدء المعالجة'
    )
    completed_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='وقت الإنجاز'
    )
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='%(class)s_completions',
        verbose_name='أنجز بواسطة'
    )

    # فلتر الإدارة
    department_filter = models.CharField(
        max_length=100, blank=True, null=True,
        choices=Department.choices,
        verbose_name='الإدارة المسؤولة'
    )

    # التواريخ
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاريخ الإنشاء'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='تاريخ التحديث'
    )

    class Meta:
        abstract = True
        ordering = ['-created_at']


# ==============================
# ملفات إضافة الموظفين / Employee Files
# ==============================

class EmployeeFile(BaseRequest):
    """
    ملفات إضافة الموظفين - يطابق جدول employee_files
    يحتوي على بيانات الموظف الأساسية وملف التعيين
    """
    employee_name = models.CharField(
        max_length=100,
        verbose_name='اسم الموظف'
    )
    employee_number = models.CharField(
        max_length=50, blank=True, null=True,
        verbose_name='رقم الموظف', db_index=True
    )
    start_type = models.CharField(
        max_length=20, choices=StartType.choices,
        default=StartType.NEW,
        verbose_name='نوع البداية'
    )
    national_id = models.CharField(
        max_length=20, blank=True, null=True,
        verbose_name='رقم الهوية', db_index=True
    )
    nationality = models.CharField(
        max_length=50, blank=True, null=True,
        verbose_name='الجنسية'
    )
    start_date = models.DateField(
        null=True, blank=True,
        verbose_name='تاريخ المباشرة'
    )
    salary = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True,
        verbose_name='الراتب الأساسي'
    )
    housing_allowance = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='بدل سكن'
    )
    transport_allowance = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='بدل نقل'
    )
    other_allowances = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='بدلات أخرى'
    )
    overtime_allowance = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='بدل عمل إضافي'
    )
    insurance_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name='نسبة التأمين'
    )
    external_allowance = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='بدل خارجي'
    )
    branch = models.ForeignKey(
        'Branch', to_field='name', db_column='branch',
        on_delete=models.SET_NULL, null=True, blank=True,
        db_constraint=False, verbose_name='الفرع'
    )
    department = models.CharField(
        max_length=100, blank=True, null=True,
        verbose_name='القسم'
    )
    cost_center = models.ForeignKey(
        'CostCenter', to_field='name', db_column='cost_center',
        on_delete=models.SET_NULL, null=True, blank=True,
        db_constraint=False, verbose_name='مركز التكلفة'
    )
    organization = models.ForeignKey(
        'Organization', to_field='name', db_column='organization',
        on_delete=models.SET_NULL, null=True, blank=True,
        db_constraint=False, verbose_name='المؤسسة'
    )
    sponsorship = models.ForeignKey(
        'Sponsorship', to_field='name', db_column='sponsorship',
        on_delete=models.SET_NULL, null=True, blank=True,
        db_constraint=False, verbose_name='الكفالة'
    )
    
    INSURANCE_CATEGORY_CHOICES = [
        ('VVIP', 'VVIP'),
        ('A', 'A'),
        ('B3', 'B3'),
        ('MP2', 'MP2'),
        ('MP3', 'MP3'),
        ('MP4', 'MP4'),
    ]
    insurance_category = models.CharField(
        max_length=10, choices=INSURANCE_CATEGORY_CHOICES,
        blank=True, null=True, verbose_name='فئة التأمين'
    )
    is_suspended = models.BooleanField(
        default=False, verbose_name='موقوف'
    )
    suspended_from = models.DateField(
        null=True, blank=True, verbose_name='تاريخ الإيقاف'
    )
    is_on_leave = models.BooleanField(
        default=False, verbose_name='إجازة'
    )
    leave_from = models.DateField(
        null=True, blank=True, verbose_name='تاريخ بداية الإجازة'
    )
    file_path = models.FileField(
        upload_to=upload_to, blank=True, null=True,
        validators=[FileExtensionValidator(
            allowed_extensions=['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'xls', 'xlsx']
        )],
        verbose_name='الملف المرفق'
    )
    file_name = models.CharField(
        max_length=255, blank=True, null=True,
        verbose_name='اسم الملف'
    )
    notes = models.TextField(
        blank=True, null=True,
        verbose_name='ملاحظات'
    )
    assigned_employee_number = models.CharField(
        max_length=50, blank=True, null=True,
        verbose_name='رقم الموظف المعيّن'
    )

    class Meta:
        verbose_name = 'ملف موظف'
        verbose_name_plural = 'ملفات الموظفين'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['employee_name'], name='idx_ef_emp_name'),
            models.Index(fields=['status'], name='idx_ef_status'),
        ]

    def __str__(self):
        return f"{self.employee_name} - {self.employee_number or 'بدون رقم'}"


# ==============================
# ملفات السلف / Advance Files
# ==============================

class AdvanceFile(BaseRequest):
    """
    طلبات السلف - يطابق جدول advance_files
    يتعامل مع طلبات السلف المالية للموظفين
    """
    employee_name = models.CharField(
        max_length=100,
        verbose_name='اسم الموظف'
    )
    employee_number = models.CharField(
        max_length=50, blank=True, null=True,
        verbose_name='رقم الموظف'
    )
    advance_amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        verbose_name='مبلغ السلفة',
        validators=[MinValueValidator(0)]
    )
    advance_date = models.DateField(
        null=True, blank=True,
        verbose_name='تاريخ السلفة'
    )
    branch = models.ForeignKey(
        'Branch', to_field='name', db_column='branch',
        on_delete=models.SET_NULL, null=True, blank=True,
        db_constraint=False, verbose_name='الفرع'
    )
    file_path = models.FileField(
        upload_to=upload_to, blank=True, null=True,
        validators=[FileExtensionValidator(
            allowed_extensions=['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'xls', 'xlsx']
        )],
        verbose_name='الملف المرفق'
    )
    file_name = models.CharField(
        max_length=255, blank=True, null=True,
        verbose_name='اسم الملف'
    )
    notes = models.TextField(
        blank=True, null=True,
        verbose_name='ملاحظات'
    )
    installments = models.PositiveIntegerField(
        default=1,
        verbose_name='عدد الأقساط'
    )

    class Meta:
        verbose_name = 'طلب سلفة'
        verbose_name_plural = 'طلبات السلف'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['employee_name'], name='idx_af_emp_name'),
            models.Index(fields=['status'], name='idx_af_status'),
        ]

    def __str__(self):
        return f"{self.employee_name} - {self.advance_amount} ر.س"


# ==============================
# ملفات الإفادات (الإجازات) / Statement Files
# ==============================

class StatementFile(BaseRequest):
    """
    الإفادات والإجازات - يطابق جدول statement_files
    يتعامل مع طلبات الإجازات والإفادات
    """
    employee_name = models.CharField(
        max_length=100,
        verbose_name='اسم الموظف'
    )
    employee_number = models.CharField(
        max_length=50, blank=True, null=True,
        verbose_name='رقم الموظف'
    )
    statement_type = models.CharField(
        max_length=100,
        verbose_name='نوع الإفادة'
    )
    branch = models.ForeignKey(
        'Branch', to_field='name', db_column='branch',
        on_delete=models.SET_NULL, null=True, blank=True,
        db_constraint=False, verbose_name='الفرع'
    )
    vacation_days = models.IntegerField(
        null=True, blank=True,
        verbose_name='عدد أيام الإجازة',
        validators=[MinValueValidator(1)]
    )
    vacation_start = models.DateField(
        null=True, blank=True,
        verbose_name='بداية الإجازة'
    )
    vacation_end = models.DateField(
        null=True, blank=True,
        verbose_name='نهاية الإجازة'
    )
    vacation_balance = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True,
        verbose_name='رصيد الإجازات'
    )
    file_path = models.FileField(
        upload_to=upload_to, blank=True, null=True,
        validators=[FileExtensionValidator(
            allowed_extensions=['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'xls', 'xlsx']
        )],
        verbose_name='الملف المرفق'
    )
    file_name = models.CharField(
        max_length=255, blank=True, null=True,
        verbose_name='اسم الملف'
    )
    notes = models.TextField(
        blank=True, null=True,
        verbose_name='ملاحظات'
    )

    class Meta:
        verbose_name = 'طلب إجازة'
        verbose_name_plural = 'طلبات الإجازة'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['statement_type'], name='idx_sf_type'),
            models.Index(fields=['status'], name='idx_sf_status'),
        ]

    def __str__(self):
        return f"{self.employee_name} - {self.statement_type}"


# ==============================
# ملفات المخالفات / Violation Files
# ==============================

class ViolationFile(BaseRequest):
    """
    المخالفات والجزاءات - يطابق جدول violation_files
    يتعامل مع تسجيل المخالفات الإدارية
    """
    violation_type = models.CharField(
        max_length=100,
        verbose_name='نوع المخالفة'
    )
    employee_name = models.CharField(
        max_length=100,
        verbose_name='اسم الموظف'
    )
    employee_number = models.CharField(
        max_length=50, blank=True, null=True,
        verbose_name='رقم الموظف'
    )
    violation_date = models.DateField(
        null=True, blank=True,
        verbose_name='تاريخ المخالفة'
    )
    branch = models.ForeignKey(
        'Branch', to_field='name', db_column='branch',
        on_delete=models.SET_NULL, null=True, blank=True,
        db_constraint=False, verbose_name='الفرع'
    )
    employee_branch = models.ForeignKey(
        'Branch', to_field='name', db_column='employee_branch', related_name='+',
        on_delete=models.SET_NULL, null=True, blank=True,
        db_constraint=False, verbose_name='فرع الموظف'
    )
    employee_department = models.CharField(
        max_length=100, blank=True, null=True,
        verbose_name='إدارة الموظف'
    )
    file_path = models.FileField(
        upload_to=upload_to, blank=True, null=True,
        validators=[FileExtensionValidator(
            allowed_extensions=['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'xls', 'xlsx']
        )],
        verbose_name='الملف المرفق'
    )
    violation_notes = models.TextField(
        blank=True, null=True,
        verbose_name='ملاحظات المخالفة'
    )
    employee_statement = models.TextField(
        blank=True, null=True,
        verbose_name='إفادة الموظف'
    )

    class Meta:
        verbose_name = 'مخالفة'
        verbose_name_plural = 'المخالفات'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['violation_type'], name='idx_vf_type'),
            models.Index(fields=['status'], name='idx_vf_status'),
        ]

    def __str__(self):
        return f"{self.employee_name} - {self.violation_type}"


# ==============================
# ملفات إنهاء الخدمات / Termination Files
# ==============================

class TerminationFile(BaseRequest):
    """
    إنهاء خدمات الموظفين - يطابق جدول termination_files
    """
    employee_name = models.CharField(
        max_length=100,
        verbose_name='اسم الموظف'
    )
    employee_number = models.CharField(
        max_length=50, blank=True, null=True,
        verbose_name='رقم الموظف'
    )
    national_id = models.CharField(
        max_length=20, blank=True, null=True,
        verbose_name='رقم الهوية'
    )
    nationality = models.CharField(
        max_length=50, blank=True, null=True,
        verbose_name='الجنسية'
    )
    branch = models.ForeignKey(
        'Branch', to_field='name', db_column='branch',
        on_delete=models.SET_NULL, null=True, blank=True,
        db_constraint=False, verbose_name='الفرع'
    )
    file_path = models.FileField(
        upload_to=upload_to, blank=True, null=True,
        validators=[FileExtensionValidator(
            allowed_extensions=['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'xls', 'xlsx']
        )],
        verbose_name='الملف المرفق'
    )
    last_working_date = models.DateField(
        blank=True, null=True,
        verbose_name='آخر تاريخ عمل'
    )
    notes = models.TextField(
        blank=True, null=True,
        verbose_name='ملاحظات'
    )

    class Meta:
        verbose_name = 'إنهاء خدمة'
        verbose_name_plural = 'إنهاءات الخدمات'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status'], name='idx_tf_status'),
        ]

    def __str__(self):
        return f"{self.employee_name} - {self.national_id or ''}"


# ==============================
# التأمين الطبي / Medical Insurance
# ==============================

class MedicalInsurance(BaseRequest):
    """
    التأمين الطبي - يطابق جدول medical_insurance
    """
    insurance_type = models.CharField(
        max_length=100,
        verbose_name='نوع التأمين'
    )
    employee_name = models.CharField(
        max_length=100,
        verbose_name='اسم الموظف'
    )
    details = models.TextField(
        verbose_name='التفاصيل'
    )
    branch = models.ForeignKey(
        'Branch', to_field='name', db_column='branch',
        on_delete=models.SET_NULL, null=True, blank=True,
        db_constraint=False, verbose_name='الفرع'
    )
    file_path = models.FileField(
        upload_to=upload_to, blank=True, null=True,
        validators=[FileExtensionValidator(
            allowed_extensions=['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'xls', 'xlsx']
        )],
        verbose_name='الملف المرفق'
    )

    class Meta:
        verbose_name = 'تأمين طبي'
        verbose_name_plural = 'التأمينات الطبية'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.employee_name} - {self.insurance_type}"


# ==============================
# الأعذار الطبية / Medical Excuses
# ==============================

class MedicalExcuse(BaseRequest):
    """
    الأعذار الطبية - يطابق جدول medical_excuses
    """
    employee_name = models.CharField(
        max_length=255,
        verbose_name='اسم الموظف'
    )
    employee_id_number = models.CharField(
        max_length=100,
        verbose_name='رقم الموظف', db_index=True
    )
    branch = models.CharField(
        max_length=255,
        verbose_name='الفرع', db_index=True
    )
    department = models.CharField(
        max_length=255,
        verbose_name='القسم'
    )
    cost_center = models.ForeignKey(
        'CostCenter', to_field='name', db_column='cost_center',
        on_delete=models.SET_NULL, null=True, blank=True,
        db_constraint=False, verbose_name='مركز التكلفة'
    )
    excuse_reason = models.TextField(
        verbose_name='سبب العذر الطبي'
    )
    excuse_date = models.DateField(
        null=True, blank=True,
        verbose_name='تاريخ العذر'
    )
    excuse_duration = models.IntegerField(
        default=1,
        verbose_name='مدة العذر (أيام)',
        validators=[MinValueValidator(1)]
    )
    file_path = models.FileField(
        upload_to=upload_to, blank=True, null=True,
        validators=[FileExtensionValidator(
            allowed_extensions=['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'xls', 'xlsx']
        )],
        verbose_name='الملف المرفق'
    )

    class Meta:
        verbose_name = 'عذر طبي'
        verbose_name_plural = 'الأعذار الطبية'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status'], name='idx_me_status'),
            models.Index(fields=['branch'], name='idx_me_branch'),
        ]

    def __str__(self):
        return f"{self.employee_name} - {self.excuse_date}"


# ==============================
# تعديلات الرواتب / Salary Adjustments
# ==============================

class SalaryAdjustment(BaseRequest):
    """
    تعديلات الرواتب - يطابق جدول salary_adjustments
    """
    employee_ref = models.ForeignKey(
        'EmployeeFile', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='salary_adjustments',
        verbose_name='ملف الموظف'
    )
    employee_number = models.CharField(
        max_length=50,
        verbose_name='رقم الموظف', db_index=True
    )
    employee_name = models.CharField(
        max_length=255,
        verbose_name='اسم الموظف'
    )
    branch = models.ForeignKey(
        'Branch', to_field='name', db_column='branch',
        on_delete=models.SET_NULL, null=True, blank=True,
        db_constraint=False, verbose_name='الفرع'
    )
    department = models.CharField(
        max_length=100, blank=True, null=True,
        verbose_name='القسم'
    )
    cost_center = models.ForeignKey(
        'CostCenter', to_field='name', db_column='cost_center',
        on_delete=models.SET_NULL, null=True, blank=True,
        db_constraint=False, verbose_name='مركز التكلفة'
    )
    current_salary = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='الراتب الحالي',
        validators=[MinValueValidator(0)]
    )
    salary_increase = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='الزيادة'
    )
    new_salary = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='الراتب الجديد',
        validators=[MinValueValidator(0)]
    )
    installments = models.PositiveIntegerField(
        default=1,
        verbose_name='عدد الأقساط'
    )
    adjustment_reason = models.TextField(
        blank=True, null=True,
        verbose_name='سبب التعديل'
    )
    notes = models.TextField(
        blank=True, null=True,
        verbose_name='ملاحظات'
    )

    class Meta:
        verbose_name = 'تعديل راتب'
        verbose_name_plural = 'تعديلات الرواتب'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['employee_number'], name='idx_sa_emp_num'),
            models.Index(fields=['status'], name='idx_sa_status'),
        ]

    def __str__(self):
        return f"{self.employee_name}: {self.current_salary} → {self.new_salary}"

    def save(self, *args, **kwargs):
        """حساب الراتب الجديد تلقائياً عند الحفظ"""
        if self.current_salary and self.salary_increase:
            self.new_salary = self.current_salary + self.salary_increase
        super().save(*args, **kwargs)


# ==============================
# طلبات النقل / Transfer Requests
# ==============================

class EmployeeTransferRequest(BaseRequest):
    """
    طلبات نقل الموظفين - يطابق جدول employee_transfer_requests
    """
    employee_name = models.CharField(
        max_length=100,
        verbose_name='اسم الموظف'
    )
    employee_id_number = models.CharField(
        max_length=50,
        verbose_name='رقم الموظف', db_index=True
    )
    current_branch = models.ForeignKey(
        'Branch', to_field='name', db_column='current_branch', related_name='+',
        on_delete=models.SET_NULL, null=True, blank=True,
        db_constraint=False, verbose_name='الفرع الحالي'
    )
    requested_branch = models.ForeignKey(
        'Branch', to_field='name', db_column='requested_branch', related_name='+',
        on_delete=models.SET_NULL, null=True, blank=True,
        db_constraint=False, verbose_name='الفرع المطلوب'
    )
    current_department = models.CharField(
        max_length=100,
        verbose_name='القسم الحالي'
    )
    requested_department = models.CharField(
        max_length=100,
        verbose_name='القسم المطلوب'
    )
    current_cost_center = models.ForeignKey(
        'CostCenter', to_field='name', db_column='current_cost_center', related_name='+',
        on_delete=models.SET_NULL, null=True, blank=True,
        db_constraint=False, verbose_name='مركز التكلفة الحالي'
    )
    new_cost_center = models.ForeignKey(
        'CostCenter', to_field='name', db_column='new_cost_center', related_name='+',
        on_delete=models.SET_NULL, null=True, blank=True,
        db_constraint=False, verbose_name='مركز التكلفة الجديد'
    )
    transfer_reason = models.TextField(
        verbose_name='سبب النقل'
    )
    preferred_date = models.DateField(
        null=True, blank=True,
        verbose_name='التاريخ المفضل'
    )

    class Meta:
        verbose_name = 'طلب نقل'
        verbose_name_plural = 'طلبات النقل'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status'], name='idx_etr_status'),
        ]

    def __str__(self):
        return f"{self.employee_name}: {self.current_branch} → {self.requested_branch}"


# ==============================
# سجلات الحضور / Attendance Records
# ==============================

class AttendanceRecord(BaseRequest):
    """
    سجلات الحضور - يطابق جدول attendance_records
    يدعم معالجة الحضور بالدفعات.
    يرث من BaseRequest لتوحيد سلسلة الاعتمادات الثلاثية.
    """
    batch_id = models.CharField(
        max_length=100, blank=True, null=True,
        verbose_name='رقم الدفعة', db_index=True
    )
    batch_date = models.DateField(
        null=True, blank=True,
        verbose_name='تاريخ الدفعة'
    )
    employee_name = models.CharField(
        max_length=255,
        verbose_name='اسم الموظف'
    )
    title = models.CharField(
        max_length=255, blank=True, null=True,
        verbose_name='المسمى الوظيفي'
    )
    branch = models.ForeignKey(
        'Branch', to_field='name', db_column='branch',
        on_delete=models.SET_NULL, null=True, blank=True,
        db_constraint=False, verbose_name='الفرع'
    )
    date_from = models.DateField(
        null=True, blank=True,
        verbose_name='من تاريخ'
    )
    attendance_date = models.DateField(
        null=True, blank=True,
        verbose_name='تاريخ الحضور', db_index=True
    )
    shift_start = models.TimeField(
        null=True, blank=True,
        verbose_name='بداية الوردية'
    )
    shift_end = models.TimeField(
        null=True, blank=True,
        verbose_name='نهاية الوردية'
    )
    nationality = models.CharField(
        max_length=50, blank=True, null=True,
        verbose_name='الجنسية'
    )
    notes = models.TextField(
        blank=True, null=True,
        verbose_name='ملاحظات'
    )

    # ملاحظة: حقول الاعتماد (status, branch_manager_approval, إلخ)
    # موروثة من BaseRequest - لا حاجة لإعادة تعريفها

    class Meta:
        verbose_name = 'سجل حضور'
        verbose_name_plural = 'سجلات الحضور'
        ordering = ['-attendance_date', '-created_at']
        indexes = [
            models.Index(fields=['batch_id'], name='idx_att_batch'),
            models.Index(fields=['attendance_date'], name='idx_att_date'),
            models.Index(fields=['status'], name='idx_att_status'),
        ]

    def __str__(self):
        return f"{self.employee_name} - {self.attendance_date}"


# ==============================
# رسائل النظام / System Messages
# ==============================

class SystemMessage(models.Model):
    """
    رسائل النظام - يطابق جدول system_messages
    رسائل البث من مدير النظام لجميع المستخدمين
    """
    title = models.CharField(
        max_length=255,
        verbose_name='العنوان'
    )
    content = models.TextField(
        verbose_name='المحتوى'
    )
    message_type = models.CharField(
        max_length=20, choices=MessageType.choices,
        default=MessageType.INFO,
        verbose_name='نوع الرسالة'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='نشطة'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='system_messages',
        verbose_name='أنشئت بواسطة'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاريخ الإنشاء'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='تاريخ التحديث'
    )

    class Meta:
        verbose_name = 'رسالة نظام'
        verbose_name_plural = 'رسائل النظام'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_message_type_display()}] {self.title}"


# ==============================
# الإشعارات / Notifications
# ==============================

class Notification(models.Model):
    """
    الإشعارات - يطابق جدول notifications
    إشعارات فردية لكل مستخدم
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name='المستخدم', db_index=True
    )
    title = models.CharField(
        max_length=255,
        verbose_name='العنوان'
    )
    message = models.TextField(
        verbose_name='الرسالة'
    )
    notification_type = models.CharField(
        max_length=20, choices=MessageType.choices,
        default=MessageType.INFO,
        verbose_name='النوع'
    )
    link = models.CharField(
        max_length=500, blank=True, null=True,
        verbose_name='الرابط'
    )
    icon = models.CharField(
        max_length=100, blank=True, null=True,
        verbose_name='الأيقونة'
    )
    is_read = models.BooleanField(
        default=False,
        verbose_name='مقروءة', db_index=True
    )
    read_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='تاريخ القراءة'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاريخ الإنشاء', db_index=True
    )

    class Meta:
        verbose_name = 'إشعار'
        verbose_name_plural = 'الإشعارات'
        ordering = ['-created_at']

    def __str__(self):
        status = '✓' if self.is_read else '●'
        return f"{status} {self.title} ({self.user})"

    def mark_as_read(self):
        """تعليم الإشعار كمقروء"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])


# ==============================
# رسائل المستخدمين / User Messages
# ==============================

class MessageStatus(models.TextChoices):
    OPEN = 'open', 'مفتوحة'
    CLOSED = 'closed', 'مغلقة'


class UserMessage(models.Model):
    """
    رسائل المستخدمين - يطابق جدول messages
    تواصل بين المستخدمين (طلبات/استفسارات)
    """
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='sent_messages',
        verbose_name='المرسل'
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='received_messages',
        verbose_name='المستقبل'
    )
    message_text = models.TextField(
        verbose_name='نص الرسالة'
    )
    status = models.CharField(
        max_length=20, choices=MessageStatus.choices,
        default=MessageStatus.OPEN,
        verbose_name='الحالة'
    )
    reply_text = models.TextField(
        blank=True, null=True,
        verbose_name='نص الرد'
    )
    reply_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='message_replies',
        verbose_name='الرد بواسطة'
    )
    reply_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='تاريخ الرد'
    )
    reply_file_path = models.CharField(
        max_length=255, blank=True, null=True,
        verbose_name='ملف مرفق بالرد'
    )
    sent_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاريخ الإرسال'
    )

    class Meta:
        verbose_name = 'رسالة'
        verbose_name_plural = 'الرسائل'
        ordering = ['-sent_at']

    def __str__(self):
        status_icon = '✓' if self.status == MessageStatus.CLOSED else '●'
        return f"{status_icon} من {self.sender} إلى {self.receiver}"


# ==============================
# سجل النشاطات / Activity Log
# ==============================

class ActivityLog(models.Model):
    """
    سجل النشاطات - يطابق جدول activity_logs
    تسجيل كامل لجميع العمليات في النظام
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='activity_logs',
        verbose_name='المستخدم', db_index=True
    )
    username = models.CharField(
        max_length=50, blank=True, null=True,
        verbose_name='اسم المستخدم'
    )
    action = models.CharField(
        max_length=50, choices=ActivityAction.choices,
        verbose_name='العملية', db_index=True
    )
    module = models.CharField(
        max_length=100,
        verbose_name='الوحدة', db_index=True
    )
    description = models.TextField(
        blank=True, null=True,
        verbose_name='الوصف'
    )
    target_id = models.IntegerField(
        null=True, blank=True,
        verbose_name='معرف الهدف', db_index=True
    )
    old_data = models.JSONField(
        null=True, blank=True,
        verbose_name='البيانات القديمة'
    )
    new_data = models.JSONField(
        null=True, blank=True,
        verbose_name='البيانات الجديدة'
    )
    ip_address = models.GenericIPAddressField(
        null=True, blank=True,
        verbose_name='عنوان IP'
    )
    user_agent = models.TextField(
        blank=True, null=True,
        verbose_name='المتصفح'
    )
    request_url = models.CharField(
        max_length=500, blank=True, null=True,
        verbose_name='رابط الطلب'
    )
    request_method = models.CharField(
        max_length=10, blank=True, null=True,
        verbose_name='نوع الطلب'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاريخ الإنشاء', db_index=True
    )

    class Meta:
        verbose_name = 'سجل نشاط'
        verbose_name_plural = 'سجل النشاطات'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.username} - {self.get_action_display()} - {self.module}"


# ==============================
# الأقسام (جدول منفصل) / Departments Table
# ==============================

class DepartmentModel(models.Model):
    """
    الأقسام - جدول منفصل لإدارة الأقسام والإدارات
    """
    name = models.CharField(
        max_length=150, unique=True,
        verbose_name='اسم القسم'
    )
    code = models.CharField(
        max_length=20, unique=True, blank=True, null=True,
        verbose_name='رمز القسم'
    )
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='managed_departments',
        verbose_name='مدير القسم'
    )
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sub_departments',
        verbose_name='القسم الرئيسي'
    )
    description = models.TextField(
        blank=True, null=True,
        verbose_name='الوصف'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='نشط'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاريخ الإنشاء'
    )

    class Meta:
        verbose_name = 'قسم'
        verbose_name_plural = 'الأقسام'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def employee_count(self):
        return self.payroll_employees.filter(is_active=True).count()


# ==============================
# كشوف الرواتب / Payroll
# ==============================

class PayrollPeriodChoices(models.TextChoices):
    MONTHLY = 'monthly', 'شهري'
    WEEKLY = 'weekly', 'أسبوعي'
    BIWEEKLY = 'biweekly', 'نصف شهري'


class PayrollStatusChoices(models.TextChoices):
    DRAFT = 'draft', 'مسودة'
    PENDING = 'pending', 'بانتظار الاعتماد'
    APPROVED = 'approved', 'معتمد'
    PAID = 'paid', 'مدفوع'
    CANCELLED = 'cancelled', 'ملغي'


class Payroll(models.Model):
    """
    كشف الرواتب الشهري - يربط الموظف بالراتب والخصومات
    """
    employee = models.ForeignKey(
        'EmployeeFile', on_delete=models.CASCADE,
        related_name='payroll_records',
        verbose_name='الموظف'
    )
    department = models.ForeignKey(
        DepartmentModel, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='payroll_employees',
        verbose_name='القسم'
    )
    period_month = models.PositiveIntegerField(
        verbose_name='الشهر',
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    period_year = models.PositiveIntegerField(
        verbose_name='السنة'
    )
    basic_salary = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='الراتب الأساسي',
        validators=[MinValueValidator(0)]
    )
    housing_allowance = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='بدل سكن',
        validators=[MinValueValidator(0)]
    )
    transport_allowance = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='بدل نقل',
        validators=[MinValueValidator(0)]
    )
    other_allowances = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='بدلات أخرى',
        validators=[MinValueValidator(0)]
    )
    overtime_hours = models.DecimalField(
        max_digits=6, decimal_places=2, default=0,
        verbose_name='ساعات إضافية',
        validators=[MinValueValidator(0)]
    )
    overtime_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='مبلغ الساعات الإضافية',
        validators=[MinValueValidator(0)]
    )
    deductions = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='الخصومات',
        validators=[MinValueValidator(0)]
    )
    social_insurance = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='التأمينات الاجتماعية',
        validators=[MinValueValidator(0)]
    )
    absence_deduction = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='خصم الغياب',
        validators=[MinValueValidator(0)]
    )
    advance_deduction = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='خصم السلف',
        validators=[MinValueValidator(0)]
    )
    net_salary = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='صافي الراتب'
    )
    status = models.CharField(
        max_length=20, choices=PayrollStatusChoices.choices,
        default=PayrollStatusChoices.DRAFT,
        verbose_name='الحالة', db_index=True
    )
    notes = models.TextField(
        blank=True, null=True,
        verbose_name='ملاحظات'
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_payrolls',
        verbose_name='اعتمد بواسطة'
    )
    approved_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='تاريخ الاعتماد'
    )
    paid_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='تاريخ الصرف'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_payrolls',
        verbose_name='أنشئ بواسطة'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاريخ الإنشاء'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='تاريخ التحديث'
    )

    class Meta:
        verbose_name = 'كشف راتب'
        verbose_name_plural = 'كشوف الرواتب'
        ordering = ['-period_year', '-period_month']
        unique_together = ['employee', 'period_month', 'period_year']
        indexes = [
            models.Index(fields=['period_year', 'period_month'], name='idx_payroll_period'),
            models.Index(fields=['status'], name='idx_payroll_status'),
        ]

    def __str__(self):
        return f"{self.employee.employee_name} - {self.period_month}/{self.period_year}"

    @property
    def total_earnings(self):
        return (
            self.basic_salary + self.housing_allowance +
            self.transport_allowance + self.other_allowances +
            self.overtime_amount
        )

    @property
    def total_deductions(self):
        return (
            self.deductions + self.social_insurance +
            self.absence_deduction + self.advance_deduction
        )

    def calculate_net_salary(self):
        """حساب صافي الراتب (لا يقل عن صفر)"""
        net = self.total_earnings - self.total_deductions
        self.net_salary = max(net, Decimal('0'))
        return self.net_salary

    def save(self, *args, **kwargs):
        self.calculate_net_salary()
        super().save(*args, **kwargs)


# ==============================
# تقييم الأداء / Performance Reviews
# ==============================

class PerformanceRating(models.TextChoices):
    EXCELLENT = 'excellent', 'ممتاز'
    VERY_GOOD = 'very_good', 'جيد جداً'
    GOOD = 'good', 'جيد'
    ACCEPTABLE = 'acceptable', 'مقبول'
    POOR = 'poor', 'ضعيف'


class PerformanceReview(models.Model):
    """
    تقييم الأداء - تقييم دوري للموظفين
    """
    employee = models.ForeignKey(
        'EmployeeFile', on_delete=models.CASCADE,
        related_name='performance_reviews',
        verbose_name='الموظف'
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviews_given',
        verbose_name='المُقيّم'
    )
    review_period_start = models.DateField(
        verbose_name='بداية فترة التقييم'
    )
    review_period_end = models.DateField(
        verbose_name='نهاية فترة التقييم'
    )

    # معايير التقييم (1-5)
    work_quality = models.PositiveIntegerField(
        verbose_name='جودة العمل',
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        default=3
    )
    productivity = models.PositiveIntegerField(
        verbose_name='الإنتاجية',
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        default=3
    )
    teamwork = models.PositiveIntegerField(
        verbose_name='العمل الجماعي',
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        default=3
    )
    punctuality = models.PositiveIntegerField(
        verbose_name='الالتزام بالمواعيد',
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        default=3
    )
    initiative = models.PositiveIntegerField(
        verbose_name='المبادرة',
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        default=3
    )
    communication = models.PositiveIntegerField(
        verbose_name='التواصل',
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        default=3
    )

    overall_rating = models.CharField(
        max_length=20, choices=PerformanceRating.choices,
        default=PerformanceRating.GOOD,
        verbose_name='التقييم العام'
    )
    score = models.DecimalField(
        max_digits=4, decimal_places=2, default=0,
        verbose_name='الدرجة الإجمالية'
    )
    strengths = models.TextField(
        blank=True, null=True,
        verbose_name='نقاط القوة'
    )
    weaknesses = models.TextField(
        blank=True, null=True,
        verbose_name='نقاط الضعف'
    )
    goals = models.TextField(
        blank=True, null=True,
        verbose_name='الأهداف المستقبلية'
    )
    reviewer_comments = models.TextField(
        blank=True, null=True,
        verbose_name='ملاحظات المُقيّم'
    )
    employee_comments = models.TextField(
        blank=True, null=True,
        verbose_name='تعليق الموظف'
    )
    is_acknowledged = models.BooleanField(
        default=False,
        verbose_name='تم الاطلاع'
    )
    acknowledged_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='تاريخ الاطلاع'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاريخ الإنشاء'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='تاريخ التحديث'
    )

    class Meta:
        verbose_name = 'تقييم أداء'
        verbose_name_plural = 'تقييمات الأداء'
        ordering = ['-review_period_end']
        indexes = [
            models.Index(fields=['overall_rating'], name='idx_perf_rating'),
        ]

    def __str__(self):
        return f"{self.employee.employee_name} - {self.get_overall_rating_display()} ({self.review_period_end})"

    def calculate_score(self):
        """حساب متوسط الدرجة من معايير التقييم"""
        criteria = [
            self.work_quality, self.productivity, self.teamwork,
            self.punctuality, self.initiative, self.communication
        ]
        self.score = sum(criteria) / len(criteria)
        # تحديد التقييم العام
        if self.score >= 4.5:
            self.overall_rating = PerformanceRating.EXCELLENT
        elif self.score >= 3.5:
            self.overall_rating = PerformanceRating.VERY_GOOD
        elif self.score >= 2.5:
            self.overall_rating = PerformanceRating.GOOD
        elif self.score >= 1.5:
            self.overall_rating = PerformanceRating.ACCEPTABLE
        else:
            self.overall_rating = PerformanceRating.POOR
        return self.score

    def save(self, *args, **kwargs):
        self.calculate_score()
        super().save(*args, **kwargs)

# ==============================
# الفروع ومراكز التكلفة (مستوردة من الجذر القديم)
# ==============================

class Branch(models.Model):
    name = models.CharField(max_length=150, unique=True, verbose_name='اسم الفرع')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')

    class Meta:
        verbose_name = 'فرع'
        verbose_name_plural = 'الفروع'
        ordering = ['name']

    def __str__(self):
        return self.name


class CostCenter(models.Model):
    name = models.CharField(max_length=150, unique=True, verbose_name='اسم مركز التكلفة')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')

    class Meta:
        verbose_name = 'مركز تكلفة'
        verbose_name_plural = 'مراكز التكلفة'
        ordering = ['name']

    def __str__(self):
        return self.name


class Organization(models.Model):
    """جدول المؤسسات"""
    name = models.CharField(max_length=150, unique=True, verbose_name='اسم المؤسسة')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')

    class Meta:
        verbose_name = 'مؤسسة'
        verbose_name_plural = 'المؤسسات'
        ordering = ['name']

    def __str__(self):
        return self.name


class Sponsorship(models.Model):
    """جدول الكفالات"""
    name = models.CharField(max_length=150, unique=True, verbose_name='اسم الكفالة')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')

    class Meta:
        verbose_name = 'كفالة'
        verbose_name_plural = 'الكفالات'
        ordering = ['name']

    def __str__(self):
        return self.name


class WorkerStatusLog(models.Model):
    """سجل حالات العمال (إيقاف/إجازة)"""
    
    STATUS_CHOICES = [
        ('suspended', 'موقوف'),
        ('leave', 'إجازة'),
    ]
    
    employee = models.ForeignKey(
        'EmployeeFile', on_delete=models.CASCADE,
        related_name='status_logs', verbose_name='الموظف'
    )
    status_type = models.CharField(
        max_length=20, choices=STATUS_CHOICES, verbose_name='نوع الحالة'
    )
    start_date = models.DateField(verbose_name='تاريخ البداية')
    end_date = models.DateField(
        null=True, blank=True, verbose_name='تاريخ النهاية'
    )
    is_active = models.BooleanField(
        default=True, verbose_name='نشط'
    )
    reason = models.TextField(
        blank=True, null=True, verbose_name='السبب'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='أنشئ بواسطة'
    )

    class Meta:
        verbose_name = 'سجل حالة عامل'
        verbose_name_plural = 'سجل حالات العمال'
        ordering = ['-start_date', '-created_at']

    def __str__(self):
        status = dict(self.STATUS_CHOICES).get(self.status_type, self.status_type)
        return f"{self.employee.employee_name} - {status} من {self.start_date}"
    
    def get_excluded_days(self, period_start, period_end):
        """
        حساب عدد الأيام المستبعدة من الراتب ضمن فترة معينة
        """
        if not self.is_active and not self.end_date:
            return 0
            
        # تحديد بداية ونهاية الفترة المستبعدة
        exclude_start = max(self.start_date, period_start)
        exclude_end = self.end_date if self.end_date else period_end
        exclude_end = min(exclude_end, period_end)
        
        if exclude_start > exclude_end:
            return 0
            
        return (exclude_end - exclude_start).days + 1
