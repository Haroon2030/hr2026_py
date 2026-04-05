"""
أمر إنشاء المدير الأول للنظام
================================
يُنشئ مستخدم مدير (superuser) مع صلاحيات كاملة
الاستخدام: python manage.py setup_admin
"""

from django.core.management.base import BaseCommand
from apps.core.models import User, UserRole


class Command(BaseCommand):
    help = 'إنشاء مستخدم مدير أولي للنظام'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, default='admin')
        parser.add_argument('--password', type=str, default='admin123')
        parser.add_argument('--email', type=str, default='admin@hr.com')
        parser.add_argument('--name', type=str, default='مدير النظام')

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        email = options['email']
        full_name = options['name']

        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'⚠️ المستخدم "{username}" موجود مسبقاً')
            )
            return

        name_parts = full_name.split(' ', 1)
        user = User.objects.create_superuser(
            username=username,
            password=password,
            email=email,
            first_name=name_parts[0],
            last_name=name_parts[1] if len(name_parts) > 1 else '',
            role=UserRole.ADMIN,
            is_staff=True,
        )

        self.stdout.write(self.style.SUCCESS(
            f'✅ تم إنشاء المدير بنجاح:\n'
            f'   اسم المستخدم: {username}\n'
            f'   كلمة المرور: {password}\n'
            f'   البريد: {email}\n'
            f'   ⚠️ يرجى تغيير كلمة المرور فوراً!'
        ))
