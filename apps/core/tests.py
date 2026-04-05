"""
اختبارات نظام الموارد البشرية
=================================
"""

from decimal import Decimal
from django.test import TestCase

from apps.core.models import (
    User, EmployeeFile, AdvanceFile,
    SalaryAdjustment, UserRole, RequestStatus, ApprovalStatus,
)


class UserModelTest(TestCase):
    """اختبار نموذج المستخدم"""

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='admin', password='test123',
            email='admin@test.com', role=UserRole.ADMIN
        )
        self.employee = User.objects.create_user(
            username='emp1', password='test123',
            first_name='محمد', last_name='أحمد',
            role=UserRole.BRANCH_EMPLOYEE
        )

    def test_user_creation(self):
        self.assertEqual(User.objects.count(), 2)
        self.assertTrue(self.admin.is_admin_role)
        self.assertFalse(self.employee.is_admin_role)

    def test_user_roles(self):
        self.assertEqual(self.admin.role, UserRole.ADMIN)
        self.assertEqual(self.employee.role, UserRole.BRANCH_EMPLOYEE)

    def test_user_str(self):
        self.assertIn('محمد', str(self.employee))


class EmployeeFileTest(TestCase):
    """اختبار نموذج ملفات الموظفين"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='uploader', password='test123'
        )
        self.emp = EmployeeFile.objects.create(
            employee_name='أحمد محمد',
            employee_number='EMP001',
            national_id='1234567890',
            salary=5000,
            branch='الرياض',
            department='تقنية المعلومات',
            uploaded_by=self.user,
        )

    def test_employee_creation(self):
        self.assertEqual(EmployeeFile.objects.count(), 1)
        self.assertEqual(self.emp.status, RequestStatus.PENDING)

    def test_approval_defaults(self):
        self.assertEqual(self.emp.branch_manager_approval, ApprovalStatus.PENDING)
        self.assertEqual(self.emp.department_manager_approval, ApprovalStatus.PENDING)
        self.assertEqual(self.emp.manager_approval, ApprovalStatus.PENDING)

    def test_str(self):
        self.assertIn('أحمد محمد', str(self.emp))


class SalaryAdjustmentTest(TestCase):
    """اختبار نموذج تعديلات الرواتب"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='hr_user', password='test123'
        )

    def test_salary_calculation(self):
        adj = SalaryAdjustment(
            employee_name='خالد',
            employee_number='EMP002',
            current_salary=Decimal('5000.00'),
            salary_increase=Decimal('500.00'),
            uploaded_by=self.user,
        )
        adj.save()
        self.assertEqual(adj.new_salary, Decimal('5500.00'))

    def test_str(self):
        adj = SalaryAdjustment.objects.create(
            employee_name='سالم',
            employee_number='EMP003',
            current_salary=Decimal('4000.00'),
            salary_increase=Decimal('300.00'),
            new_salary=Decimal('4300.00'),
            uploaded_by=self.user,
        )
        self.assertIn('4000', str(adj))
        self.assertIn('4300', str(adj))


class AdvanceFileTest(TestCase):
    """اختبار نموذج طلبات السلف"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='adv_user', password='test123'
        )

    def test_advance_creation(self):
        adv = AdvanceFile.objects.create(
            employee_name='عبدالله',
            advance_amount=Decimal('2000.00'),
            branch='جدة',
            uploaded_by=self.user,
        )
        self.assertEqual(adv.status, RequestStatus.PENDING)
        self.assertIn('2000', str(adv))
