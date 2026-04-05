# Generated manually - إصلاح AttendanceRecord ليرث من BaseRequest
# يُضيف الحقول الناقصة من BaseRequest ويُصحح max_length لحقل status

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_alter_statementfile_options'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── 1. تصحيح max_length لحقل status (50 → 20 مطابق لـ BaseRequest) ──
        migrations.AlterField(
            model_name='attendancerecord',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'معلّق'),
                    ('in_progress', 'قيد المعالجة'),
                    ('completed', 'مكتمل'),
                    ('approved', 'معتمد'),
                    ('rejected', 'مرفوض'),
                ],
                db_index=True,
                default='pending',
                max_length=20,
                verbose_name='الحالة',
            ),
        ),

        # ── 2. إضافة الحقول الناقصة من BaseRequest ──

        migrations.AddField(
            model_name='attendancerecord',
            name='branch_approved_by',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='attendancerecord_branch_approvals',
                to=settings.AUTH_USER_MODEL,
                verbose_name='معتمد من مدير الفرع',
            ),
        ),
        migrations.AddField(
            model_name='attendancerecord',
            name='department_approved_by',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='attendancerecord_dept_approvals',
                to=settings.AUTH_USER_MODEL,
                verbose_name='معتمد من مدير الإدارة',
            ),
        ),
        migrations.AddField(
            model_name='attendancerecord',
            name='manager_approved_by',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='attendancerecord_mgr_approvals',
                to=settings.AUTH_USER_MODEL,
                verbose_name='معتمد من المدير العام',
            ),
        ),
        migrations.AddField(
            model_name='attendancerecord',
            name='assign_note',
            field=models.TextField(blank=True, null=True, verbose_name='ملاحظة التكليف'),
        ),
        migrations.AddField(
            model_name='attendancerecord',
            name='in_progress_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='وقت بدء المعالجة'),
        ),
        migrations.AddField(
            model_name='attendancerecord',
            name='completed_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='وقت الإنجاز'),
        ),
        migrations.AddField(
            model_name='attendancerecord',
            name='completed_by',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='attendancerecord_completions',
                to=settings.AUTH_USER_MODEL,
                verbose_name='أنجز بواسطة',
            ),
        ),
        migrations.AddField(
            model_name='attendancerecord',
            name='department_filter',
            field=models.CharField(
                blank=True, null=True, max_length=100,
                choices=[
                    ('purchasing', 'إدارة المشتريات'),
                    ('financial', 'إدارة المالية'),
                    ('technical', 'إدارة التقنية'),
                    ('data', 'إدارة البيانات'),
                ],
                verbose_name='الإدارة المسؤولة',
            ),
        ),

        # ── 3. تحديث related_name لـ assigned_to (attendancerecord_assignments) ──
        migrations.AlterField(
            model_name='attendancerecord',
            name='assigned_to',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='attendancerecord_assignments',
                to=settings.AUTH_USER_MODEL,
                verbose_name='معيّن إلى',
            ),
        ),

        # ── 4. تحديث related_name لـ uploaded_by (attendancerecord_uploads) ──
        migrations.AlterField(
            model_name='attendancerecord',
            name='uploaded_by',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='attendancerecord_uploads',
                to=settings.AUTH_USER_MODEL,
                verbose_name='رُفع بواسطة',
            ),
        ),
    ]
