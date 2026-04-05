"""
نماذج قسم المالية
==================
PayrollPeriod : فترة الرواتب الشهرية - مدخل توليد الرواتب
PayrollProxy  : proxy لعرض كشوف الرواتب تحت قسم المالية
"""
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator

from apps.core.models import Payroll


# ──────────────────────────────────────────────
# إعدادات المالية العامة
# ──────────────────────────────────────────────

class FinanceSettings(models.Model):
    """
    إعدادات قسم المالية - Singleton Pattern
    """
    saudi_social_insurance_rate = models.DecimalField(
        max_digits=5, decimal_places=4, default=0.0900,
        verbose_name='نسبة التأمينات (سعودي)',
        help_text='مثال: 0.09 تعني 9%'
    )
    non_saudi_social_insurance_rate = models.DecimalField(
        max_digits=5, decimal_places=4, default=0.0000,
        verbose_name='نسبة التأمينات (غير سعودي)',
        help_text='مثال: 0.00 تعني 0%'
    )

    class Meta:
        verbose_name = 'إعدادات المالية'
        verbose_name_plural = 'إعدادات المالية'
        app_label = 'payroll'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "إعدادات المالية العامة"


# ──────────────────────────────────────────────
# حالات فترة الرواتب
# ──────────────────────────────────────────────

class PeriodStatus(models.TextChoices):
    OPEN       = 'open',       'مفتوحة'
    GENERATED  = 'generated',  'تم التوليد'
    APPROVED   = 'approved',   'معتمدة'
    PAID       = 'paid',       'تم الصرف'
    CLOSED     = 'closed',     'مغلقة'


# ──────────────────────────────────────────────
# فترة الرواتب الشهرية
# ──────────────────────────────────────────────

class PayrollPeriod(models.Model):
    """
    فترة الرواتب الشهرية.
    كل فترة تمثل شهراً ميلادياً، وتُستخدم لتوليد كشوف رواتب
    جميع الموظفين النشطين (المعتمدين) الذين بدأ تعيينهم قبل أو خلال هذا الشهر.
    """

    month = models.PositiveIntegerField(
        verbose_name='الشهر',
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )
    year = models.PositiveIntegerField(
        verbose_name='السنة',
        validators=[MinValueValidator(2020), MaxValueValidator(2099)],
    )
    status = models.CharField(
        max_length=20,
        choices=PeriodStatus.choices,
        default=PeriodStatus.OPEN,
        verbose_name='الحالة',
        db_index=True,
    )
    notes = models.TextField(blank=True, null=True, verbose_name='ملاحظات')

    # ── إحصائيات التوليد ──────────────────────
    generated_employees = models.PositiveIntegerField(
        default=0,
        verbose_name='عدد الموظفين المُولَّدة رواتبهم',
    )
    skipped_employees = models.PositiveIntegerField(
        default=0,
        verbose_name='موظفون تم تخطيهم (موجودون مسبقاً)',
    )
    total_basic = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='إجمالي الرواتب الأساسية',
    )
    total_net = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='إجمالي الصافي',
    )
    excel_file = models.FileField(
        upload_to='payroll_excel/%Y/',
        null=True, blank=True,
        verbose_name='ملف الإكسيل المولد',
    )

    # ── من قام بالتوليد ───────────────────────
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='generated_payroll_periods',
        verbose_name='ولّده',
    )
    generated_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='تاريخ التوليد',
    )

    # ── من اعتمد / صرف ────────────────────────
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_payroll_periods',
        verbose_name='اعتمده',
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الاعتماد')
    paid_at     = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الصرف')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True,     verbose_name='تاريخ التحديث')

    class Meta:
        verbose_name        = 'فترة رواتب'
        verbose_name_plural = 'فترات الرواتب'
        unique_together     = ['month', 'year']
        ordering            = ['-year', '-month']
        app_label           = 'payroll'

    def __str__(self):
        months_ar = {
            1:'يناير', 2:'فبراير', 3:'مارس', 4:'أبريل',
            5:'مايو', 6:'يونيو', 7:'يوليو', 8:'أغسطس',
            9:'سبتمبر', 10:'أكتوبر', 11:'نوفمبر', 12:'ديسمبر',
        }
        return f"{months_ar.get(self.month, self.month)} {self.year}"

    @property
    def month_label(self):
        return self.__str__()


# ──────────────────────────────────────────────
# Proxy لكشوف الرواتب تحت قسم المالية
# ──────────────────────────────────────────────

class PayrollProxy(Payroll):
    """
    Proxy model يجعل كشوف الرواتب تظهر تحت قسم "المالية"
    في الشريط الجانبي بدلاً من "إدارة النظام".
    """
    class Meta:
        proxy               = True
        verbose_name        = 'كشف راتب'
        verbose_name_plural = 'كشوف الرواتب'
        app_label           = 'payroll'
