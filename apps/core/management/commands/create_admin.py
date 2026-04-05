"""
إنشاء مستخدم Admin تلقائياً
استخدام: python manage.py create_admin
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os


class Command(BaseCommand):
    help = 'إنشاء مستخدم admin إذا لم يكن موجوداً'

    def handle(self, *args, **options):
        User = get_user_model()
        
        username = os.getenv('ADMIN_USERNAME', 'admin')
        email = os.getenv('ADMIN_EMAIL', 'admin@example.com')
        password = os.getenv('ADMIN_PASSWORD', 'admin123')
        
        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'المستخدم "{username}" موجود مسبقاً')
            )
            return
        
        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password
        )
        
        self.stdout.write(
            self.style.SUCCESS(f'✓ تم إنشاء المستخدم Admin: {username}')
        )
        self.stdout.write(f'   البريد: {email}')
        self.stdout.write(f'   كلمة المرور: {password}')
