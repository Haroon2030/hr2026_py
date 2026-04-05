"""
Custom AdminSite with Dashboard
================================
يعرض لوحة المعلومات كصفحة رئيسية للإدارة
"""

from django.contrib.admin import AdminSite
from django.db.models import Count, Sum, Avg
from django.utils import timezone


class HRAdminSite(AdminSite):
    site_header = "نظام الموارد البشرية - HR Pro"
    site_title = "HR Pro Admin"
    index_title = "لوحة المعلومات"
    index_template = 'admin/dashboard.html'
    # Disable Django's built-in collapsible nav sidebar (we have our own in base.html)
    enable_nav_sidebar = False

    def index(self, request, extra_context=None):
        from .models import (
            User, EmployeeFile, AdvanceFile, StatementFile,
            ViolationFile, TerminationFile, MedicalInsurance,
            MedicalExcuse, SalaryAdjustment, EmployeeTransferRequest,
            AttendanceRecord, Notification, ActivityLog,
            Payroll, PerformanceReview, DepartmentModel,
            RequestStatus, ApprovalStatus,
            PayrollStatusChoices,
        )

        today = timezone.now().date()
        month_start = today.replace(day=1)

        # إحصائيات عامة
        total_employees = EmployeeFile.objects.filter(
            status__in=[RequestStatus.APPROVED, RequestStatus.COMPLETED]
        ).count()
        total_users = User.objects.filter(is_active=True).count()
        total_departments = DepartmentModel.objects.filter(is_active=True).count()

        # الطلبات المعلقة
        pending_requests = {
            'employees': EmployeeFile.objects.filter(status=RequestStatus.PENDING).count(),
            'advances': AdvanceFile.objects.filter(status=RequestStatus.PENDING).count(),
            'statements': StatementFile.objects.filter(status=RequestStatus.PENDING).count(),
            'violations': ViolationFile.objects.filter(status=RequestStatus.PENDING).count(),
            'terminations': TerminationFile.objects.filter(status=RequestStatus.PENDING).count(),
            'medical_insurance': MedicalInsurance.objects.filter(status=RequestStatus.PENDING).count(),
            'medical_excuses': MedicalExcuse.objects.filter(status=RequestStatus.PENDING).count(),
            'salary_adjustments': SalaryAdjustment.objects.filter(status=RequestStatus.PENDING).count(),
            'transfers': EmployeeTransferRequest.objects.filter(status=RequestStatus.PENDING).count(),
        }
        total_pending = sum(pending_requests.values())

        # إحصائيات الحضور
        today_attendance = AttendanceRecord.objects.filter(
            attendance_date=today
        ).count()

        # إحصائيات الرواتب
        current_month_payroll = Payroll.objects.filter(
            period_month=today.month, period_year=today.year
        )
        payroll_stats = current_month_payroll.aggregate(
            total_net=Sum('net_salary'),
            total_basic=Sum('basic_salary'),
            count=Count('id'),
        )
        paid_payroll = current_month_payroll.filter(
            status=PayrollStatusChoices.PAID
        ).count()

        # إحصائيات الأداء
        performance_stats = PerformanceReview.objects.aggregate(
            avg_score=Avg('score'),
            total=Count('id'),
        )
        performance_by_rating = list(
            PerformanceReview.objects.values('overall_rating').annotate(
                count=Count('id')
            ).order_by('overall_rating')
        )

        # آخر النشاطات
        recent_activities = ActivityLog.objects.select_related('user').order_by(
            '-created_at'
        )[:10]

        # الإشعارات غير المقروءة
        unread_notifications = 0
        if request.user.is_authenticated:
            unread_notifications = Notification.objects.filter(
                user=request.user, is_read=False
            ).count()

        # بيانات الرسم البياني
        monthly_requests = []
        models_for_chart = [
            ('ملفات موظفين', EmployeeFile),
            ('سلف', AdvanceFile),
            ('إجازات', StatementFile),
            ('مخالفات', ViolationFile),
            ('تأمينات', MedicalInsurance),
            ('نقل', EmployeeTransferRequest),
        ]
        for label, model in models_for_chart:
            count = model.objects.filter(created_at__date__gte=month_start).count()
            monthly_requests.append({'label': label, 'count': count})

        # طلبات تحتاج اعتماد
        needs_approval_count = 0
        user_role = getattr(request.user, 'role', '')
        approval_field_map = {
            'branch_manager': 'branch_manager_approval',
            'department_manager': 'department_manager_approval',
            'manager': 'manager_approval',
            'admin': 'manager_approval',
        }
        approval_field = approval_field_map.get(user_role)
        if approval_field:
            for model in [EmployeeFile, AdvanceFile, StatementFile,
                          ViolationFile, TerminationFile, MedicalInsurance,
                          MedicalExcuse, SalaryAdjustment, EmployeeTransferRequest]:
                needs_approval_count += model.objects.filter(
                    **{approval_field: ApprovalStatus.PENDING}
                ).count()

        # --- New customized admin dashboard variables ---
        advances_sum = AdvanceFile.objects.filter(status__in=[RequestStatus.APPROVED, RequestStatus.COMPLETED]).aggregate(s=Sum('advance_amount'))['s'] or 0
        new_employees = EmployeeFile.objects.filter(status=RequestStatus.PENDING).count()
        approved_employees = total_employees
        leaving_employees = TerminationFile.objects.filter(status__in=[RequestStatus.PENDING, RequestStatus.APPROVED]).count()

        transfers_count = pending_requests.get('transfers', 0)
        advances_count = pending_requests.get('advances', 0)
        terminations_count = pending_requests.get('terminations', 0)
        
        oldest_transfer_days = 0
        oldest_tr = EmployeeTransferRequest.objects.filter(status=RequestStatus.PENDING).order_by('created_at').first()
        if oldest_tr:
            oldest_transfer_days = (timezone.now() - oldest_tr.created_at).days

        dashboard_context = {
            'total_employees': total_employees,
            'total_users': total_users,
            'total_departments': total_departments,
            'total_pending': total_pending,
            'pending_requests': pending_requests,
            'today_attendance': today_attendance,
            'payroll_total_net': payroll_stats['total_net'] or 0,
            'payroll_total_basic': payroll_stats['total_basic'] or 0,
            'payroll_count': payroll_stats['count'] or 0,
            'paid_payroll': paid_payroll,
            'performance_avg': performance_stats['avg_score'] or 0,
            'performance_total': performance_stats['total'] or 0,
            'performance_by_rating': performance_by_rating,
            'recent_activities': recent_activities,
            'unread_notifications': unread_notifications,
            'monthly_requests': monthly_requests,
            'needs_approval_count': needs_approval_count,
            'today': today,
            'current_month': today.month,
            'current_year': today.year,
            
            # --- New custom elements ---
            'advances_sum': advances_sum,
            'new_employees': new_employees,
            'approved_employees': approved_employees,
            'leaving_employees': leaving_employees,
            'transfers_count': transfers_count,
            'oldest_transfer_days': oldest_transfer_days,
            'advances_count': advances_count,
            'advances_pending_sum': AdvanceFile.objects.filter(status=RequestStatus.PENDING).aggregate(s=Sum('advance_amount'))['s'] or 0,
            'terminations_count': terminations_count,
        }

        extra_context = extra_context or {}
        extra_context.update(dashboard_context)
        return super().index(request, extra_context=extra_context)

    def get_urls(self):
        from django.urls import path
        from django.http import JsonResponse
        from .models import EmployeeFile, RequestStatus

        def search_employees_view(request):
            if not request.user.is_staff:
                return JsonResponse({'error': 'Unauthorized'}, status=403)
            q = request.GET.get('q', '').strip()
            qs = EmployeeFile.objects.filter(
                status__in=[RequestStatus.APPROVED, RequestStatus.COMPLETED]
            )
            if q:
                qs = qs.filter(
                    employee_name__icontains=q
                ) | EmployeeFile.objects.filter(
                    status__in=[RequestStatus.APPROVED, RequestStatus.COMPLETED],
                    employee_number__icontains=q,
                )
            qs = qs.values('employee_name', 'employee_number', 'branch__name', 'department')[:30]
            results = [
                {
                    'name': e['employee_name'],
                    'number': e['employee_number'] or '',
                    'branch': e['branch__name'] or '',
                    'department': e['department'] or '',
                }
                for e in qs
            ]
            return JsonResponse({'results': results})

        def quick_termination_view(request):
            """حفظ طلب إنهاء خدمة مباشرة مع جلب بيانات الموظف"""
            import json
            from .models import TerminationFile, EmployeeFile, RequestStatus

            if not request.user.is_staff:
                return JsonResponse({'error': 'Unauthorized'}, status=403)
            if request.method != 'POST':
                return JsonResponse({'error': 'Method not allowed'}, status=405)

            try:
                data = json.loads(request.body)
            except Exception:
                return JsonResponse({'error': 'بيانات غير صالحة'}, status=400)

            employee_number = data.get('employee_number', '').strip()
            employee_name = data.get('employee_name', '').strip()
            last_working_date = data.get('last_working_date', '').strip()

            if not employee_name or not last_working_date:
                return JsonResponse({'error': 'اسم الموظف وآخر تاريخ عمل مطلوبان'}, status=400)

            # جلب بيانات الموظف الكاملة من ملفاته
            emp = None
            if employee_number:
                emp = EmployeeFile.objects.filter(
                    employee_number=employee_number,
                    status__in=[RequestStatus.APPROVED, RequestStatus.COMPLETED]
                ).order_by('-created_at').first()
            if not emp:
                emp = EmployeeFile.objects.filter(
                    employee_name=employee_name,
                    status__in=[RequestStatus.APPROVED, RequestStatus.COMPLETED]
                ).order_by('-created_at').first()

            # بناء بيانات الطلب
            termination_data = {
                'employee_name': employee_name,
                'employee_number': employee_number,
                'last_working_date': last_working_date,
                'uploaded_by': request.user,
                'status': RequestStatus.PENDING,
            }
            if emp:
                termination_data['national_id'] = emp.national_id or ''
                termination_data['nationality'] = emp.nationality or ''
                if emp.branch_id:
                    termination_data['branch_id'] = emp.branch_id

            try:
                term = TerminationFile.objects.create(**termination_data)
            except Exception as e:
                return JsonResponse({'error': 'خطأ أثناء الحفظ: ' + str(e)}, status=500)

            view_url = '/requests/terminationfileproxy/{}/change/'.format(term.pk)
            return JsonResponse({
                'success': True,
                'message': 'تم حفظ طلب إنهاء الخدمة بنجاح',
                'id': term.pk,
                'view_url': view_url,
            })

        def quick_salary_adjustment_view(request):
            """حفظ تعديل راتب سريع مع جلب بيانات الموظف"""
            import json
            from .models import SalaryAdjustment, EmployeeFile, RequestStatus

            if not request.user.is_staff:
                return JsonResponse({'error': 'Unauthorized'}, status=403)
            if request.method != 'POST':
                return JsonResponse({'error': 'Method not allowed'}, status=405)

            try:
                data = json.loads(request.body)
            except Exception:
                return JsonResponse({'error': 'بيانات غير صالحة'}, status=400)

            employee_number = str(data.get('employee_number', '')).strip()
            employee_name   = str(data.get('employee_name', '')).strip()
            salary_increase = data.get('salary_increase', '')

            if not employee_name or salary_increase == '' or salary_increase is None:
                return JsonResponse({'error': 'اسم الموظف ومبلغ الزيادة مطلوبان'}, status=400)

            try:
                salary_increase = float(salary_increase)
            except (ValueError, TypeError):
                return JsonResponse({'error': 'قيم غير صالحة'}, status=400)

            if salary_increase <= 0:
                return JsonResponse({'error': 'مبلغ الزيادة يجب أن يكون أكبر من صفر'}, status=400)

            # جلب بيانات الموظف من ملفاته
            emp = None
            if employee_number:
                emp = EmployeeFile.objects.filter(
                    employee_number=employee_number,
                    status__in=[RequestStatus.APPROVED, RequestStatus.COMPLETED]
                ).order_by('-created_at').first()
            if not emp:
                emp = EmployeeFile.objects.filter(
                    employee_name=employee_name,
                    status__in=[RequestStatus.APPROVED, RequestStatus.COMPLETED]
                ).order_by('-created_at').first()

            current_salary = float(emp.salary) if emp and emp.salary else 0.0
            new_salary = current_salary + salary_increase

            adjustment_data = {
                'employee_name': employee_name,
                'employee_number': employee_number,
                'current_salary': current_salary,
                'salary_increase': salary_increase,
                'new_salary': new_salary,
                'installments': 1,
                'uploaded_by': request.user,
                'status': RequestStatus.PENDING,
            }
            if emp:
                adjustment_data['employee_ref'] = emp
                adjustment_data['department'] = emp.department or ''
                if emp.branch_id:
                    adjustment_data['branch_id'] = emp.branch_id
                if emp.cost_center_id:
                    adjustment_data['cost_center_id'] = emp.cost_center_id

            try:
                adj = SalaryAdjustment.objects.create(**adjustment_data)
            except Exception as e:
                return JsonResponse({'error': 'خطأ أثناء الحفظ: ' + str(e)}, status=500)

            view_url = '/requests/salaryadjustmentproxy/{}/change/'.format(adj.pk)
            return JsonResponse({
                'success': True,
                'message': 'تم حفظ طلب تعديل الراتب بنجاح',
                'id': adj.pk,
                'view_url': view_url,
                'current_salary': current_salary,
                'new_salary': new_salary,
            })

        def quick_advance_view(request):
            """حفظ طلب سلفة سريع"""
            import json
            from .models import AdvanceFile, EmployeeFile, RequestStatus
            from datetime import date

            if not request.user.is_staff:
                return JsonResponse({'error': 'Unauthorized'}, status=403)
            if request.method != 'POST':
                return JsonResponse({'error': 'Method not allowed'}, status=405)

            try:
                data = json.loads(request.body)
            except Exception:
                return JsonResponse({'error': 'بيانات غير صالحة'}, status=400)

            employee_number = str(data.get('employee_number', '')).strip()
            employee_name   = str(data.get('employee_name', '')).strip()
            advance_amount  = data.get('advance_amount', '')
            installments    = data.get('installments', 1)

            if not employee_name or advance_amount == '' or advance_amount is None:
                return JsonResponse({'error': 'اسم الموظف ومبلغ السلفة مطلوبان'}, status=400)

            try:
                advance_amount = float(advance_amount)
                installments = int(installments)
            except (ValueError, TypeError):
                return JsonResponse({'error': 'قيم غير صالحة'}, status=400)

            if advance_amount <= 0:
                return JsonResponse({'error': 'مبلغ السلفة يجب أن يكون أكبر من صفر'}, status=400)
            if installments < 1:
                installments = 1

            # جلب بيانات الموظف من ملفاته
            emp = None
            if employee_number:
                emp = EmployeeFile.objects.filter(
                    employee_number=employee_number,
                    status__in=[RequestStatus.APPROVED, RequestStatus.COMPLETED]
                ).order_by('-created_at').first()
            if not emp:
                emp = EmployeeFile.objects.filter(
                    employee_name=employee_name,
                    status__in=[RequestStatus.APPROVED, RequestStatus.COMPLETED]
                ).order_by('-created_at').first()

            advance_data = {
                'employee_name': employee_name,
                'employee_number': employee_number,
                'advance_amount': advance_amount,
                'advance_date': date.today(),
                'installments': installments,
                'uploaded_by': request.user,
                'status': RequestStatus.PENDING,
            }
            if emp:
                if emp.branch_id:
                    advance_data['branch_id'] = emp.branch_id

            try:
                adv = AdvanceFile.objects.create(**advance_data)
            except Exception as e:
                return JsonResponse({'error': 'خطأ أثناء الحفظ: ' + str(e)}, status=500)

            view_url = '/requests/advancefileproxy/{}/change/'.format(adv.pk)
            return JsonResponse({
                'success': True,
                'message': 'تم حفظ طلب السلفة بنجاح',
                'id': adv.pk,
                'view_url': view_url,
                'advance_amount': advance_amount,
                'installments': installments,
            })

        def quick_vacation_view(request):
            """حفظ طلب إجازة سريع مع حساب الرصيد"""
            import json
            from .models import StatementFile, EmployeeFile, RequestStatus
            from datetime import date, timedelta
            from decimal import Decimal

            if not request.user.is_staff:
                return JsonResponse({'error': 'Unauthorized'}, status=403)
            if request.method != 'POST':
                return JsonResponse({'error': 'Method not allowed'}, status=405)

            try:
                data = json.loads(request.body)
            except Exception:
                return JsonResponse({'error': 'بيانات غير صالحة'}, status=400)

            employee_number = str(data.get('employee_number', '')).strip()
            employee_name   = str(data.get('employee_name', '')).strip()
            vacation_start  = data.get('vacation_start', '')
            vacation_days   = data.get('vacation_days', '')
            notes           = str(data.get('notes', '')).strip()

            if not employee_name or not vacation_start or vacation_days == '' or vacation_days is None:
                return JsonResponse({'error': 'اسم الموظف وتاريخ البداية وعدد الأيام مطلوبة'}, status=400)

            try:
                vacation_days = int(vacation_days)
            except (ValueError, TypeError):
                return JsonResponse({'error': 'عدد الأيام غير صالح'}, status=400)

            if vacation_days < 1:
                return JsonResponse({'error': 'عدد الأيام يجب أن يكون 1 على الأقل'}, status=400)

            # جلب بيانات الموظف من ملفاته
            emp = None
            if employee_number:
                emp = EmployeeFile.objects.filter(
                    employee_number=employee_number,
                    status__in=[RequestStatus.APPROVED, RequestStatus.COMPLETED]
                ).order_by('-created_at').first()
            if not emp:
                emp = EmployeeFile.objects.filter(
                    employee_name=employee_name,
                    status__in=[RequestStatus.APPROVED, RequestStatus.COMPLETED]
                ).order_by('-created_at').first()

            # حساب الرصيد من تاريخ التعيين (21 يوم في السنة)
            vacation_balance = Decimal('0.00')
            if emp and emp.start_date:
                today = date.today()
                days_worked = (today - emp.start_date).days
                # استخدام 365.25 لحساب السنوات الكبيسة بدقة
                years_worked = Decimal(str(days_worked)) / Decimal('365.25')
                total_entitled = years_worked * Decimal('21')
                
                # حساب الإجازات المستخدمة سابقاً
                used_vacations = StatementFile.objects.filter(
                    employee_name=employee_name,
                    status__in=[RequestStatus.APPROVED, RequestStatus.COMPLETED],
                    vacation_days__isnull=False
                ).exclude(vacation_days__isnull=True)
                
                total_used = sum(v.vacation_days or 0 for v in used_vacations)
                vacation_balance = total_entitled - Decimal(str(total_used))
                vacation_balance = max(vacation_balance, Decimal('0.00'))

            # التحقق من أن عدد الأيام لا يتجاوز الرصيد المتاح (مقارنة عددية دقيقة)
            if vacation_balance > 0 and Decimal(str(vacation_days)) > vacation_balance:
                balance_display = float(vacation_balance)
                balance_str = f'{balance_display:.2f}'.rstrip('0').rstrip('.')
                return JsonResponse({
                    'error': f'عدد الأيام ({vacation_days}) يتجاوز الرصيد المتاح ({balance_str} يوم)'
                }, status=400)

            # حساب نهاية الإجازة
            try:
                start_date_obj = date.fromisoformat(vacation_start)
                vacation_end = start_date_obj + timedelta(days=vacation_days - 1)
            except ValueError:
                return JsonResponse({'error': 'تاريخ غير صالح'}, status=400)

            vacation_data = {
                'employee_name': employee_name,
                'employee_number': employee_number,
                'statement_type': 'إجازة سنوية',
                'vacation_start': vacation_start,
                'vacation_end': vacation_end.isoformat(),
                'vacation_days': vacation_days,
                'vacation_balance': vacation_balance,
                'notes': notes,
                'uploaded_by': request.user,
                'status': RequestStatus.PENDING,
            }
            if emp:
                if emp.branch_id:
                    vacation_data['branch_id'] = emp.branch_id

            try:
                vac = StatementFile.objects.create(**vacation_data)
            except Exception as e:
                return JsonResponse({'error': 'خطأ أثناء الحفظ: ' + str(e)}, status=500)

            view_url = '/requests/statementfileproxy/{}/change/'.format(vac.pk)
            return JsonResponse({
                'success': True,
                'message': 'تم حفظ طلب الإجازة بنجاح',
                'id': vac.pk,
                'view_url': view_url,
                'vacation_days': vacation_days,
                'vacation_balance': float(vacation_balance),
                'vacation_end': vacation_end.isoformat(),
            })

        def get_vacation_balance_view(request):
            """جلب رصيد الإجازات للموظف"""
            from .models import StatementFile, EmployeeFile, RequestStatus
            from datetime import date
            from decimal import Decimal

            if not request.user.is_staff:
                return JsonResponse({'error': 'Unauthorized'}, status=403)

            employee_name = request.GET.get('employee_name', '').strip()
            employee_number = request.GET.get('employee_number', '').strip()

            if not employee_name:
                return JsonResponse({'balance': 0})

            # جلب بيانات الموظف
            emp = None
            if employee_number:
                emp = EmployeeFile.objects.filter(
                    employee_number=employee_number,
                    status__in=[RequestStatus.APPROVED, RequestStatus.COMPLETED]
                ).order_by('-created_at').first()
            if not emp:
                emp = EmployeeFile.objects.filter(
                    employee_name=employee_name,
                    status__in=[RequestStatus.APPROVED, RequestStatus.COMPLETED]
                ).order_by('-created_at').first()

            if not emp or not emp.start_date:
                return JsonResponse({'balance': 0, 'message': 'لا يوجد تاريخ مباشرة'})

            # حساب الرصيد من تاريخ التعيين (21 يوم في السنة)
            today = date.today()
            days_worked = (today - emp.start_date).days
            # استخدام 365.25 لحساب السنوات الكبيسة بدقة
            years_worked = Decimal(str(days_worked)) / Decimal('365.25')
            total_entitled = years_worked * Decimal('21')

            # حساب الإجازات المستخدمة سابقاً
            used_vacations = StatementFile.objects.filter(
                employee_name=employee_name,
                status__in=[RequestStatus.APPROVED, RequestStatus.COMPLETED],
                vacation_days__isnull=False
            ).exclude(vacation_days__isnull=True)

            total_used = sum(v.vacation_days or 0 for v in used_vacations)
            vacation_balance = total_entitled - Decimal(str(total_used))
            vacation_balance = max(vacation_balance, Decimal('0.00'))

            return JsonResponse({
                'balance': float(vacation_balance),
                'total_entitled': float(total_entitled),
                'total_used': total_used,
                'start_date': emp.start_date.isoformat(),
            })

        def quick_violation_view(request):
            """حفظ مخالفة سريعة مع دعم رفع الملفات"""
            from .models import ViolationFile, EmployeeFile, RequestStatus
            from datetime import date

            if not request.user.is_staff:
                return JsonResponse({'error': 'Unauthorized'}, status=403)
            if request.method != 'POST':
                return JsonResponse({'error': 'Method not allowed'}, status=405)

            employee_number = request.POST.get('employee_number', '').strip()
            employee_name   = request.POST.get('employee_name', '').strip()
            violation_type  = request.POST.get('violation_type', '').strip()
            violation_date  = request.POST.get('violation_date', '').strip()
            violation_notes = request.POST.get('violation_notes', '').strip()
            uploaded_file   = request.FILES.get('file')

            if not employee_name or not violation_type:
                return JsonResponse({'error': 'اسم الموظف ونوع المخالفة مطلوبان'}, status=400)

            # جلب بيانات الموظف
            emp = None
            if employee_number:
                emp = EmployeeFile.objects.filter(
                    employee_number=employee_number,
                    status__in=[RequestStatus.APPROVED, RequestStatus.COMPLETED]
                ).order_by('-created_at').first()
            if not emp:
                emp = EmployeeFile.objects.filter(
                    employee_name=employee_name,
                    status__in=[RequestStatus.APPROVED, RequestStatus.COMPLETED]
                ).order_by('-created_at').first()

            violation_data = {
                'employee_name': employee_name,
                'employee_number': employee_number,
                'violation_type': violation_type,
                'violation_notes': violation_notes,
                'uploaded_by': request.user,
                'status': RequestStatus.PENDING,
            }
            
            if violation_date:
                violation_data['violation_date'] = violation_date
            else:
                violation_data['violation_date'] = date.today()

            if emp:
                if emp.branch_id:
                    violation_data['branch_id'] = emp.branch_id
                    violation_data['employee_branch_id'] = emp.branch_id
                if emp.department:
                    violation_data['employee_department'] = emp.department

            if uploaded_file:
                violation_data['file_path'] = uploaded_file

            try:
                viol = ViolationFile.objects.create(**violation_data)
            except Exception as e:
                return JsonResponse({'error': 'خطأ أثناء الحفظ: ' + str(e)}, status=500)

            view_url = '/requests/violationfileproxy/{}/change/'.format(viol.pk)
            return JsonResponse({
                'success': True,
                'message': 'تم حفظ المخالفة بنجاح',
                'id': viol.pk,
                'view_url': view_url,
            })

        def quick_medical_excuse_view(request):
            """حفظ عذر طبي سريع مع دعم رفع الملفات"""
            from .models import MedicalExcuse, EmployeeFile, RequestStatus
            from datetime import date

            if not request.user.is_staff:
                return JsonResponse({'error': 'Unauthorized'}, status=403)
            if request.method != 'POST':
                return JsonResponse({'error': 'Method not allowed'}, status=405)

            employee_number = request.POST.get('employee_number', '').strip()
            employee_name   = request.POST.get('employee_name', '').strip()
            employee_branch = request.POST.get('employee_branch', '').strip()
            excuse_date     = request.POST.get('excuse_date', '').strip()
            excuse_duration = request.POST.get('excuse_duration', '1').strip()
            excuse_reason   = request.POST.get('excuse_reason', '').strip()
            uploaded_file   = request.FILES.get('file')

            if not employee_name or not excuse_reason:
                return JsonResponse({'error': 'اسم الموظف وسبب العذر مطلوبان'}, status=400)

            try:
                excuse_duration = int(excuse_duration)
                if excuse_duration < 1:
                    excuse_duration = 1
            except ValueError:
                excuse_duration = 1

            # جلب بيانات الموظف
            emp = None
            if employee_number:
                emp = EmployeeFile.objects.filter(
                    employee_number=employee_number,
                    status__in=[RequestStatus.APPROVED, RequestStatus.COMPLETED]
                ).order_by('-created_at').first()
            if not emp:
                emp = EmployeeFile.objects.filter(
                    employee_name=employee_name,
                    status__in=[RequestStatus.APPROVED, RequestStatus.COMPLETED]
                ).order_by('-created_at').first()

            medical_data = {
                'employee_name': employee_name,
                'employee_id_number': employee_number,
                'excuse_reason': excuse_reason,
                'excuse_duration': excuse_duration,
                'uploaded_by': request.user,
                'status': RequestStatus.PENDING,
            }
            
            if excuse_date:
                medical_data['excuse_date'] = excuse_date
            else:
                medical_data['excuse_date'] = date.today()

            # جلب الفرع والقسم من بيانات الموظف
            if emp:
                if emp.branch_id:
                    medical_data['branch'] = emp.branch_id
                else:
                    medical_data['branch'] = employee_branch or 'غير محدد'
                medical_data['department'] = emp.department or 'غير محدد'
            else:
                medical_data['branch'] = employee_branch or 'غير محدد'
                medical_data['department'] = 'غير محدد'

            if uploaded_file:
                medical_data['file_path'] = uploaded_file

            try:
                med = MedicalExcuse.objects.create(**medical_data)
            except Exception as e:
                return JsonResponse({'error': 'خطأ أثناء الحفظ: ' + str(e)}, status=500)

            view_url = '/requests/medicalexcuseproxy/{}/change/'.format(med.pk)
            return JsonResponse({
                'success': True,
                'message': 'تم حفظ العذر الطبي بنجاح',
                'id': med.pk,
                'view_url': view_url,
            })

        def quick_transfer_view(request):
            """حفظ طلب نقل سريع مع الملء التلقائي"""
            import json
            from .models import EmployeeTransferRequest, EmployeeFile, RequestStatus
            from datetime import date

            if not request.user.is_staff:
                return JsonResponse({'error': 'Unauthorized'}, status=403)
            if request.method != 'POST':
                return JsonResponse({'error': 'Method not allowed'}, status=405)

            try:
                data = json.loads(request.body)
            except Exception:
                return JsonResponse({'error': 'بيانات غير صالحة'}, status=400)

            employee_number  = str(data.get('employee_number', '')).strip()
            employee_name    = str(data.get('employee_name', '')).strip()
            current_branch   = str(data.get('current_branch', '')).strip()
            current_department = str(data.get('current_department', '')).strip()
            new_branch       = str(data.get('new_branch', '')).strip()
            new_department   = str(data.get('new_department', '')).strip()
            transfer_date    = str(data.get('transfer_date', '')).strip()
            transfer_reason  = str(data.get('transfer_reason', '')).strip()

            if not employee_name or not new_branch or not transfer_reason:
                return JsonResponse({'error': 'اسم الموظف والفرع الجديد وسبب النقل مطلوبة'}, status=400)

            # جلب بيانات الموظف للملء التلقائي
            emp = None
            if employee_number:
                emp = EmployeeFile.objects.filter(
                    employee_number=employee_number,
                    status__in=[RequestStatus.APPROVED, RequestStatus.COMPLETED]
                ).order_by('-created_at').first()
            if not emp:
                emp = EmployeeFile.objects.filter(
                    employee_name=employee_name,
                    status__in=[RequestStatus.APPROVED, RequestStatus.COMPLETED]
                ).order_by('-created_at').first()

            transfer_data = {
                'employee_name': employee_name,
                'employee_id_number': employee_number,
                'current_department': current_department or (emp.department if emp else ''),
                'requested_department': new_department or '',
                'transfer_reason': transfer_reason,
                'uploaded_by': request.user,
                'status': RequestStatus.PENDING,
            }

            # الفرع الحالي
            if emp and emp.branch_id:
                transfer_data['current_branch_id'] = emp.branch_id
            elif current_branch:
                transfer_data['current_branch_id'] = current_branch

            # الفرع المطلوب
            if new_branch:
                transfer_data['requested_branch_id'] = new_branch

            # تاريخ النقل
            if transfer_date:
                transfer_data['preferred_date'] = transfer_date
            else:
                transfer_data['preferred_date'] = date.today()

            try:
                trans = EmployeeTransferRequest.objects.create(**transfer_data)
            except Exception as e:
                return JsonResponse({'error': 'خطأ أثناء الحفظ: ' + str(e)}, status=500)

            view_url = '/requests/employeetransferrequestproxy/{}/change/'.format(trans.pk)
            return JsonResponse({
                'success': True,
                'message': 'تم حفظ طلب النقل بنجاح',
                'id': trans.pk,
                'view_url': view_url,
            })

        def get_branches_departments_view(request):
            """جلب قائمة الفروع والأقسام"""
            from .models import Branch, DepartmentModel

            if not request.user.is_staff:
                return JsonResponse({'error': 'Unauthorized'}, status=403)

            branches = list(Branch.objects.values_list('name', flat=True).order_by('name'))
            departments = list(DepartmentModel.objects.values_list('name', flat=True).order_by('name'))

            return JsonResponse({
                'branches': branches,
                'departments': departments,
            })

        custom_urls = [
            path('search-employees/', self.admin_view(search_employees_view), name='search_employees'),
            path('quick-termination/', self.admin_view(quick_termination_view), name='quick_termination'),
            path('quick-salary-adjustment/', self.admin_view(quick_salary_adjustment_view), name='quick_salary_adjustment'),
            path('quick-advance/', self.admin_view(quick_advance_view), name='quick_advance'),
            path('quick-vacation/', self.admin_view(quick_vacation_view), name='quick_vacation'),
            path('quick-violation/', self.admin_view(quick_violation_view), name='quick_violation'),
            path('quick-medical-excuse/', self.admin_view(quick_medical_excuse_view), name='quick_medical_excuse'),
            path('quick-transfer/', self.admin_view(quick_transfer_view), name='quick_transfer'),
            path('get-vacation-balance/', self.admin_view(get_vacation_balance_view), name='get_vacation_balance'),
            path('get-branches-departments/', self.admin_view(get_branches_departments_view), name='get_branches_departments'),
        ]
        return custom_urls + super().get_urls()


hr_admin_site = HRAdminSite(name='admin')
