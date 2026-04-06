"""
الكلاسات القاعدية والفلاتر والموارد المشتركة
==============================================
تُستخدم من جميع ملفات admin الأخرى في الحزمة
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Q
from import_export import resources
from import_export.admin import ImportExportModelAdmin

from apps.core.models import (
    EmployeeFile, AdvanceFile, StatementFile,
    SalaryAdjustment, AttendanceRecord, MedicalExcuse,
    ViolationFile, EmployeeTransferRequest,
    ApprovalStatus, RequestStatus,
)


# ==============================
# Mixin لتصفية البيانات حسب الفرع والصلاحيات
# ==============================

class BranchPermissionMixin:
    """
    Mixin لتصفية البيانات حسب فرع المستخدم ومستوى صلاحياته.
    
    المستويات:
    - مدير الأدمن / Superuser: يرى كل شيء
    - مدير الموارد: يرى كل شيء
    - مدير فرع: يرى بيانات فرعه فقط (قراءة + تعديل)
    - موظف فرع: يرى بيانات فرعه فقط (قراءة فقط)
    """
    
    # اسم الحقل الذي يحتوي على الفرع في النموذج
    branch_field = 'branch'
    
    def get_queryset(self, request):
        """تصفية البيانات حسب فرع المستخدم"""
        qs = super().get_queryset(request)
        
        # السوبر أدمن أو مدير الأدمن يرى كل شيء
        if request.user.is_superuser:
            return qs
        
        # التحقق من المجموعات
        user_groups = list(request.user.groups.values_list('name', flat=True))
        
        # مدير الموارد أو مدير الأدمن يرى كل شيء
        if 'مدير الموارد' in user_groups or 'مدير الأدمن' in user_groups:
            return qs
        
        # مدير فرع أو موظف فرع - يرى فرعه فقط
        if 'مدير فرع' in user_groups or 'موظف فرع' in user_groups:
            user_branch = getattr(request.user, 'branch', None)
            if user_branch:
                # تصفية حسب الفرع
                filter_kwargs = {self.branch_field: user_branch}
                return qs.filter(**filter_kwargs)
            else:
                # إذا لم يكن للمستخدم فرع، لا يرى شيء
                return qs.none()
        
        # المستخدمين العاديين بدون مجموعة - لا يرون شيء
        return qs.none()
    
    def has_change_permission(self, request, obj=None):
        """التحقق من صلاحية التعديل"""
        if request.user.is_superuser:
            return True
        
        user_groups = list(request.user.groups.values_list('name', flat=True))
        
        # مدير الموارد ومدير الأدمن يعدلون
        if 'مدير الموارد' in user_groups or 'مدير الأدمن' in user_groups:
            return True
        
        # مدير الفرع يعدل بيانات فرعه فقط
        if 'مدير فرع' in user_groups:
            if obj is None:
                return True
            user_branch = getattr(request.user, 'branch', None)
            obj_branch = getattr(obj, self.branch_field, None)
            return user_branch == obj_branch
        
        # موظف الفرع لا يعدل
        return False
    
    def has_add_permission(self, request):
        """التحقق من صلاحية الإضافة"""
        if request.user.is_superuser:
            return True
        
        user_groups = list(request.user.groups.values_list('name', flat=True))
        
        # مدير الموارد ومدير الأدمن ومدير الفرع يضيفون
        return any(g in user_groups for g in ['مدير الموارد', 'مدير الأدمن', 'مدير فرع'])
    
    def has_delete_permission(self, request, obj=None):
        """التحقق من صلاحية الحذف"""
        if request.user.is_superuser:
            return True
        
        user_groups = list(request.user.groups.values_list('name', flat=True))
        
        # مدير الموارد ومدير الأدمن فقط يحذفون
        return 'مدير الموارد' in user_groups or 'مدير الأدمن' in user_groups
    
    def save_model(self, request, obj, form, change):
        """تعيين الفرع تلقائياً للمستخدم إذا لم يكن موجوداً"""
        if not change and not getattr(obj, self.branch_field, None):
            user_branch = getattr(request.user, 'branch', None)
            if user_branch:
                setattr(obj, self.branch_field, user_branch)
        super().save_model(request, obj, form, change)
    
    def get_list_filter(self, request):
        """إخفاء فلتر الفرع لموظفي ومديري الفروع"""
        list_filter = list(super().get_list_filter(request) or [])
        
        user_groups = list(request.user.groups.values_list('name', flat=True))
        
        # إذا كان المستخدم مدير فرع أو موظف فرع، أخفِ فلتر الفرع
        if 'مدير فرع' in user_groups or 'موظف فرع' in user_groups:
            # إزالة فلتر الفرع إن وجد
            list_filter = [f for f in list_filter if f != self.branch_field and f != 'branch']
        
        return list_filter
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """تصفية خيارات الفرع في النماذج"""
        if db_field.name == self.branch_field:
            user_groups = list(request.user.groups.values_list('name', flat=True))
            
            # مدير فرع أو موظف فرع - يرى فرعه فقط في القوائم المنسدلة
            if 'مدير فرع' in user_groups or 'موظف فرع' in user_groups:
                user_branch = getattr(request.user, 'branch', None)
                if user_branch:
                    from apps.core.models import Branch
                    kwargs['queryset'] = Branch.objects.filter(pk=user_branch.pk)
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# ==============================
# موارد التصدير والاستيراد / Import-Export Resources
# ==============================

class EmployeeFileResource(resources.ModelResource):
    """مورد تصدير/استيراد بيانات الموظفين"""
    class Meta:
        model = EmployeeFile
        fields = (
            'id', 'employee_name', 'employee_number', 'national_id',
            'nationality', 'start_date', 'salary', 'branch', 'department',
            'cost_center', 'start_type', 'status', 'created_at'
        )
        export_order = fields


class AdvanceFileResource(resources.ModelResource):
    """مورد تصدير/استيراد طلبات السلف"""
    class Meta:
        model = AdvanceFile
        fields = (
            'id', 'employee_name', 'employee_number', 'advance_amount',
            'installments', 'advance_date', 'branch', 'status', 'created_at'
        )


class StatementFileResource(resources.ModelResource):
    """مورد تصدير/استيراد الإجازات"""
    class Meta:
        model = StatementFile
        fields = (
            'id', 'employee_name', 'employee_number', 'statement_type',
            'vacation_days', 'vacation_start', 'vacation_end',
            'vacation_balance', 'branch', 'status', 'created_at'
        )


class SalaryAdjustmentResource(resources.ModelResource):
    """مورد تصدير/استيراد تعديلات الرواتب"""
    class Meta:
        model = SalaryAdjustment
        fields = (
            'id', 'employee_name', 'employee_number', 'current_salary',
            'salary_increase', 'new_salary', 'adjustment_reason',
            'branch', 'department', 'status', 'created_at'
        )


class AttendanceRecordResource(resources.ModelResource):
    """مورد تصدير/استيراد سجلات الحضور"""
    class Meta:
        model = AttendanceRecord
        fields = (
            'id', 'batch_id', 'employee_name', 'title', 'branch',
            'attendance_date', 'shift_start', 'shift_end',
            'nationality', 'notes', 'status'
        )


class MedicalExcuseResource(resources.ModelResource):
    """مورد تصدير/استيراد الأعذار الطبية"""
    class Meta:
        model = MedicalExcuse
        fields = (
            'id', 'employee_name', 'employee_id_number', 'branch',
            'department', 'excuse_reason', 'excuse_date',
            'excuse_duration', 'status', 'created_at'
        )


class ViolationFileResource(resources.ModelResource):
    """مورد تصدير/استيراد المخالفات"""
    class Meta:
        model = ViolationFile
        fields = (
            'id', 'employee_name', 'employee_number', 'violation_type',
            'violation_date', 'branch', 'status', 'created_at'
        )


class TransferRequestResource(resources.ModelResource):
    """مورد تصدير/استيراد طلبات النقل"""
    class Meta:
        model = EmployeeTransferRequest
        fields = (
            'id', 'employee_name', 'employee_id_number',
            'current_branch', 'requested_branch',
            'current_department', 'requested_department',
            'transfer_reason', 'preferred_date', 'status', 'created_at'
        )


# ==============================
# فلاتر مخصصة / Custom Filters
# ==============================

class ApprovalStatusFilter(admin.SimpleListFilter):
    """فلتر لحالة الاعتماد الشاملة - يعرض الطلبات حسب مرحلة الاعتماد"""
    title = 'مرحلة الاعتماد'
    parameter_name = 'approval_stage'

    def lookups(self, request, model_admin):
        return [
            ('needs_branch', 'بانتظار اعتماد مدير الفرع'),
            ('needs_dept', 'بانتظار اعتماد مدير الإدارة'),
            ('needs_manager', 'بانتظار اعتماد المدير العام'),
            ('fully_approved', 'معتمد بالكامل'),
            ('has_rejection', 'يحتوي على رفض'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'needs_branch':
            return queryset.filter(branch_manager_approval='pending')
        if self.value() == 'needs_dept':
            return queryset.filter(
                branch_manager_approval='approved',
                department_manager_approval='pending'
            )
        if self.value() == 'needs_manager':
            return queryset.filter(
                branch_manager_approval='approved',
                department_manager_approval='approved',
                manager_approval='pending'
            )
        if self.value() == 'fully_approved':
            return queryset.filter(
                branch_manager_approval='approved',
                department_manager_approval='approved',
                manager_approval='approved'
            )
        if self.value() == 'has_rejection':
            return queryset.filter(
                Q(branch_manager_approval='rejected') |
                Q(department_manager_approval='rejected') |
                Q(manager_approval='rejected')
            )
        return queryset


# ==============================
# كلاس قاعدي لجميع الطلبات / Base Request Admin
# ==============================

class BaseRequestAdmin(BranchPermissionMixin, ImportExportModelAdmin):
    """
    كلاس قاعدي لجميع صفحات إدارة الطلبات.
    يوفر: الإجراءات الجماعية، عرض حالة الاعتمادات، حفظ تلقائي للمستخدم.
    يرث من BranchPermissionMixin لتصفية البيانات حسب الفرع.
    """
    list_per_page = 20
    readonly_fields = (
        'created_at', 'updated_at', 'uploaded_by',
        'completed_by', 'in_progress_at', 'completed_at'
    )
    save_on_top = False
    
    # تحسين الفلاتر وجعلها قابلة للانهيار (في بعض القوالب) أو زر منسدل
    list_filter_submit = True

    class Media:
        css = {
            'all': ('css/admin_custom.css',)
        }

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/quick-approve/<str:field_name>/<str:action>/',
                self.admin_site.admin_view(self.quick_approve_view),
                name=f'{self.opts.app_label}_{self.opts.model_name}_quick_approve'
            ),
        ]
        return custom_urls + urls

    def quick_approve_view(self, request, object_id, field_name, action):
        from django.shortcuts import redirect
        from django.contrib import messages
        
        VALID_FIELDS = {'branch_manager_approval', 'department_manager_approval', 'manager_approval'}
        VALID_ACTIONS = {'approve', 'reject'}
        if field_name not in VALID_FIELDS or action not in VALID_ACTIONS:
            messages.error(request, 'إجراء غير صالح.')
            return redirect(request.META.get('HTTP_REFERER') or '..')
        
        obj = self.get_object(request, object_id)
        if obj is None:
            messages.error(request, 'الطلب غير موجود.')
            return redirect(request.META.get('HTTP_REFERER') or '..')
            
        if action == 'approve':
            setattr(obj, field_name, 'approved')
            approved_by_field = field_name.replace('_manager_approval', '_approved_by').replace('_approval', '_approved_by')
            setattr(obj, approved_by_field, request.user)
            
            # Evaluate overall status
            b = getattr(obj, 'branch_manager_approval', 'approved')
            d = getattr(obj, 'department_manager_approval', 'approved')
            m = getattr(obj, 'manager_approval', 'approved')
            if m == 'approved' and d == 'approved' and b == 'approved':
                obj.status = 'approved'
            elif field_name == 'branch_manager_approval':
                if not hasattr(obj, 'department_manager_approval'):
                    obj.status = 'approved'

            messages.success(request, 'تم الاعتماد بنجاح.')
        elif action == 'reject':
            setattr(obj, field_name, 'rejected')
            approved_by_field = field_name.replace('_manager_approval', '_approved_by').replace('_approval', '_approved_by')
            setattr(obj, approved_by_field, request.user)
            obj.status = 'rejected'
            messages.success(request, 'تم الرفض.')
            
        obj.save()
        return redirect(request.META.get('HTTP_REFERER') or '..')

    def get_approval_display(self, obj, field_name):
        from django.urls import reverse
        """عرض حالة الاعتماد بأشكال مخصصة وأزرار مباشرة"""
        value = getattr(obj, field_name)
        
        # استنتاج حقل المستخدم الذي قام بالاعتماد لمعرفة اسمه (ثامر الطريفي مثلاً)
        approved_by_field = field_name.replace('_manager_approval', '_approved_by').replace('_approval', '_approved_by')
        approved_by_obj = getattr(obj, approved_by_field, None)
        signer_name = 'معتمد'
        if approved_by_obj:
            signer_name = approved_by_obj.first_name or approved_by_obj.username

        if value == 'pending':
            try:
                url_approve = reverse(f'admin:{self.opts.app_label}_{self.opts.model_name}_quick_approve', args=[obj.pk, field_name, 'approve'])
                url_reject = reverse(f'admin:{self.opts.app_label}_{self.opts.model_name}_quick_approve', args=[obj.pk, field_name, 'reject'])
                return format_html(
                    '<div style="display:flex; gap:8px; align-items:center;">'
                    '<a href="{}" title="رفض" style="display:inline-flex; align-items:center; justify-content:center; width:34px; height:34px; background:#fff1f2; color:#e11d48; border-radius:8px; border:1px solid #ffe4e6; text-decoration:none; box-shadow: 0 4px 6px -1px rgba(225, 29, 72, 0.1);"><i class="fas fa-times"></i></a>'
                    '<a href="{}" title="اعتماد" style="display:inline-flex; align-items:center; justify-content:center; width:34px; height:34px; background:#ecfdf5; color:#059669; border-radius:8px; border:1px solid #d1fae5; text-decoration:none; box-shadow: 0 4px 6px -1px rgba(5, 150, 105, 0.1);"><i class="fas fa-check-double"></i></a>'
                    '</div>',
                    url_reject, url_approve
                )
            except Exception:
                return format_html('<span style="display:inline-flex; align-items:center; gap:4px; color:#b45309; background:#fef3c7; border:1px solid #fde68a; padding:4px 10px; border-radius:20px; font-size:11px; font-weight:700; white-space:nowrap;"><i class="fas fa-clock"></i> بانتظار الاعتماد</span>')
        elif value == 'approved':
            return format_html('<span style="display:inline-flex; align-items:center; gap:4px; color:#047857; background:#d1fae5; border:1px solid #a7f3d0; padding:4px 10px; border-radius:20px; font-size:11px; font-weight:700; white-space:nowrap;"><i class="fas fa-check-double"></i> {}</span>', signer_name)
        elif value == 'rejected':
            signer_name = approved_by_obj.first_name if approved_by_obj else 'مرفوض'
            return format_html('<span style="display:inline-flex; align-items:center; gap:4px; color:#b91c1c; background:#fee2e2; border:1px solid #fecaca; padding:4px 10px; border-radius:20px; font-size:11px; font-weight:700; white-space:nowrap;"><i class="fas fa-times"></i> {}</span>', signer_name)
        return value

    @admin.display(description='م. الفرع')
    def branch_approval_display(self, obj):
        return self.get_approval_display(obj, 'branch_manager_approval')

    @admin.display(description='م. الإدارة')
    def dept_approval_display(self, obj):
        return self.get_approval_display(obj, 'department_manager_approval')

    @admin.display(description='م. العام')
    def manager_approval_display(self, obj):
        return self.get_approval_display(obj, 'manager_approval')

    @admin.display(description='الحالة')
    def status_display(self, obj):
        val = obj.status
        if val == 'pending':
            return format_html('<span style="display:inline-flex; align-items:center; gap:4px; color:#b45309; background:#fef3c7; border:1px solid #fde68a; padding:4px 10px; border-radius:20px; font-size:11px; font-weight:700; white-space:nowrap;"><i class="fas fa-clock"></i> قيد الانتظار</span>')
        elif val == 'in_progress':
            return format_html('<span style="display:inline-flex; align-items:center; gap:4px; color:#1d4ed8; background:#dbeafe; border:1px solid #bfdbfe; padding:4px 10px; border-radius:20px; font-size:11px; font-weight:700; white-space:nowrap;"><i class="fas fa-spinner fa-spin"></i> قيد المعالجة</span>')
        elif val in ['completed', 'approved']:
            return format_html('<span style="display:inline-flex; align-items:center; gap:4px; color:#047857; background:#d1fae5; border:1px solid #a7f3d0; padding:4px 10px; border-radius:20px; font-size:11px; font-weight:700; white-space:nowrap;"><i class="fas fa-check-circle"></i> منجز</span>')
        elif val == 'rejected':
            return format_html('<span style="display:inline-flex; align-items:center; gap:4px; color:#b91c1c; background:#fee2e2; border:1px solid #fecaca; padding:4px 10px; border-radius:20px; font-size:11px; font-weight:700; white-space:nowrap;"><i class="fas fa-times-circle"></i> مرفوض</span>')
        return format_html('<span>{}</span>', obj.get_status_display())

    def save_model(self, request, obj, form, change):
        """تعيين المستخدم الذي رفع الطلب تلقائياً عند الإنشاء"""
        if not change:
            obj.uploaded_by = request.user
        # استدعاء save_model من Mixin لتعيين الفرع
        super().save_model(request, obj, form, change)

    # ==============================
    # الإجراءات الجماعية / Bulk Actions
    # ==============================

    @admin.action(description='✅ اعتماد مدير الفرع')
    def approve_branch_manager(self, request, queryset):
        updated = queryset.filter(
            branch_manager_approval=ApprovalStatus.PENDING
        ).update(
            branch_manager_approval=ApprovalStatus.APPROVED,
            branch_approved_by=request.user
        )
        self.message_user(request, f'تم اعتماد {updated} طلب/طلبات من مدير الفرع')

    @admin.action(description='❌ رفض مدير الفرع')
    def reject_branch_manager(self, request, queryset):
        updated = queryset.filter(
            branch_manager_approval=ApprovalStatus.PENDING
        ).update(
            branch_manager_approval=ApprovalStatus.REJECTED,
            branch_approved_by=request.user
        )
        self.message_user(request, f'تم رفض {updated} طلب/طلبات من مدير الفرع')

    @admin.action(description='✅ اعتماد مدير الإدارة')
    def approve_department_manager(self, request, queryset):
        updated = queryset.filter(
            department_manager_approval=ApprovalStatus.PENDING,
            branch_manager_approval=ApprovalStatus.APPROVED
        ).update(
            department_manager_approval=ApprovalStatus.APPROVED,
            department_approved_by=request.user
        )
        self.message_user(request, f'تم اعتماد {updated} طلب/طلبات من مدير الإدارة')

    @admin.action(description='❌ رفض مدير الإدارة')
    def reject_department_manager(self, request, queryset):
        updated = queryset.filter(
            department_manager_approval=ApprovalStatus.PENDING
        ).update(
            department_manager_approval=ApprovalStatus.REJECTED,
            department_approved_by=request.user
        )
        self.message_user(request, f'تم رفض {updated} طلب/طلبات من مدير الإدارة')

    @admin.action(description='✅ اعتماد المدير العام')
    def approve_general_manager(self, request, queryset):
        updated = queryset.filter(
            manager_approval=ApprovalStatus.PENDING,
            branch_manager_approval=ApprovalStatus.APPROVED,
            department_manager_approval=ApprovalStatus.APPROVED
        ).update(
            manager_approval=ApprovalStatus.APPROVED,
            manager_approved_by=request.user,
            status=RequestStatus.APPROVED
        )
        self.message_user(request, f'تم اعتماد {updated} طلب/طلبات من المدير العام')

    @admin.action(description='❌ رفض المدير العام')
    def reject_general_manager(self, request, queryset):
        updated = queryset.filter(
            manager_approval=ApprovalStatus.PENDING
        ).update(
            manager_approval=ApprovalStatus.REJECTED,
            manager_approved_by=request.user,
            status=RequestStatus.REJECTED
        )
        self.message_user(request, f'تم رفض {updated} طلب/طلبات من المدير العام')

    @admin.action(description='🔄 تحويل إلى "قيد المعالجة"')
    def mark_in_progress(self, request, queryset):
        updated = queryset.filter(
            status=RequestStatus.PENDING
        ).update(
            status=RequestStatus.IN_PROGRESS,
            in_progress_at=timezone.now(),
            assigned_to=request.user
        )
        self.message_user(request, f'تم تحديث {updated} طلب/طلبات إلى قيد المعالجة')

    @admin.action(description='✔ تحويل إلى "مكتمل"')
    def mark_completed(self, request, queryset):
        updated = queryset.exclude(
            status=RequestStatus.COMPLETED
        ).update(
            status=RequestStatus.COMPLETED,
            completed_at=timezone.now(),
            completed_by=request.user
        )
        self.message_user(request, f'تم إكمال {updated} طلب/طلبات')

    @admin.action(description='🔄 إعادة تعيين جميع الاعتمادات')
    def reset_approvals(self, request, queryset):
        updated = queryset.update(
            branch_manager_approval=ApprovalStatus.PENDING,
            department_manager_approval=ApprovalStatus.PENDING,
            manager_approval=ApprovalStatus.PENDING,
            branch_approved_by=None,
            department_approved_by=None,
            manager_approved_by=None,
            status=RequestStatus.PENDING,
        )
        self.message_user(request, f'تم إعادة تعيين الاعتمادات لـ {updated} طلب/طلبات')
