"""
أمر تنظيف السجلات القديمة
===========================
يحذف سجلات النشاطات والإشعارات القديمة للحفاظ على أداء النظام
الاستخدام: python manage.py cleanup_old_records [--days 90]
"""

from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.models import ActivityLog, Notification


class Command(BaseCommand):
    help = 'تنظيف السجلات القديمة (النشاطات والإشعارات)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', type=int, default=90,
            help='حذف السجلات الأقدم من عدد الأيام المحدد (الافتراضي: 90)'
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='عرض ما سيتم حذفه بدون تنفيذ فعلي'
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        cutoff = timezone.now() - timedelta(days=days)

        self.stdout.write(f'📅 تنظيف السجلات الأقدم من {days} يوم (قبل {cutoff.date()})')

        # تنظيف سجلات النشاط
        old_logs = ActivityLog.objects.filter(created_at__lt=cutoff)
        log_count = old_logs.count()
        if not dry_run:
            old_logs.delete()
        self.stdout.write(f'  📋 سجلات النشاط: {log_count} سجل')

        # تنظيف الإشعارات المقروءة
        old_notifs = Notification.objects.filter(
            created_at__lt=cutoff, is_read=True
        )
        notif_count = old_notifs.count()
        if not dry_run:
            old_notifs.delete()
        self.stdout.write(f'  🔔 الإشعارات المقروءة: {notif_count} إشعار')

        if dry_run:
            self.stdout.write(self.style.WARNING('🔄 تشغيل تجريبي - لم يتم حذف شيء'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'✅ تم تنظيف {log_count + notif_count} سجل بنجاح'
            ))
