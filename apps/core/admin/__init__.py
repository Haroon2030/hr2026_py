"""
حزمة إدارة نظام الموارد البشرية / HR Admin Package
=====================================================
مقسّمة إلى ملفات حسب الوحدة الوظيفية لسهولة الصيانة:

- base.py       : الكلاسات القاعدية والفلاتر والموارد المشتركة
- users.py      : إدارة المستخدمين والأدوار
- employees.py  : ملفات الموظفين وإنهاء الخدمات
- requests.py   : السلف، الإجازات، المخالفات، تعديل الرواتب، طلبات النقل
- medical.py    : التأمين الطبي والأعذار الطبية
- attendance.py : سجلات الحضور
- payroll.py    : الأقسام، كشوف الرواتب، تقييمات الأداء
- system.py     : رسائل النظام، الإشعارات، سجل النشاطات
"""

# تصدير Mixin للاستخدام في الـ proxy admins
from apps.core.admin.base import BranchPermissionMixin  # noqa: F401

# استيراد جميع الوحدات لتسجيل النماذج في Django Admin
from apps.core.admin import (  # noqa: F401
    users,
    employees,
    requests,
    medical,
    attendance,
    payroll,
    system,
)
