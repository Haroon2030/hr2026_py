"""
رفع ملفات uploads المحلية إلى Cloudflare R2
=============================================
الاستخدام:
    python manage.py upload_media_to_r2
    python manage.py upload_media_to_r2 --dry-run   # معاينة فقط
"""
import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'رفع ملفات uploads المحلية إلى R2 Storage'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='معاينة بدون رفع')
        parser.add_argument('--source', type=str, help='مسار مجلد uploads', default=None)

    def handle(self, *args, **options):
        if not getattr(settings, 'USE_R2_STORAGE', False):
            self.stderr.write("R2 Storage غير مفعّل! تحقق من USE_R2_STORAGE")
            return

        try:
            import boto3
        except ImportError:
            self.stderr.write("boto3 غير مثبت!")
            return

        dry_run = options['dry_run']
        source = options.get('source')

        # البحث عن مجلد uploads
        if not source:
            candidates = [
                Path('/app/media/uploads'),
                Path('/app/uploads'),
                settings.MEDIA_ROOT / 'uploads' if hasattr(settings, 'MEDIA_ROOT') else None,
            ]
            for c in candidates:
                if c and c.exists():
                    source = str(c)
                    break

        if not source or not Path(source).exists():
            self.stderr.write(f"مجلد uploads غير موجود!")
            return

        source_path = Path(source)

        # إعداد S3 client
        s3 = boto3.client(
            's3',
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name='auto',
        )
        bucket = settings.AWS_STORAGE_BUCKET_NAME

        # جمع الملفات
        files = list(source_path.rglob('*'))
        files = [f for f in files if f.is_file() and f.name != '.gitkeep']

        self.stdout.write(f"{'[DRY RUN] ' if dry_run else ''}رفع {len(files)} ملف إلى R2...")
        self.stdout.write(f"المصدر: {source}")
        self.stdout.write(f"الهدف: {bucket}/media/")

        uploaded = 0
        skipped = 0
        errors = 0

        # Content types
        content_types = {
            '.pdf': 'application/pdf',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xls': 'application/vnd.ms-excel',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        }

        for f in files:
            # المسار النسبي: uploads/employees/file.pdf → media/uploads/employees/file.pdf
            rel_path = f.relative_to(source_path)
            r2_key = f"media/uploads/{rel_path}"

            if dry_run:
                self.stdout.write(f"   [DRY] {r2_key}")
                uploaded += 1
                continue

            try:
                # تحقق إذا الملف موجود
                try:
                    s3.head_object(Bucket=bucket, Key=r2_key)
                    skipped += 1
                    continue
                except s3.exceptions.ClientError:
                    pass

                # رفع الملف
                ext = f.suffix.lower()
                ct = content_types.get(ext, 'application/octet-stream')

                s3.upload_file(
                    str(f),
                    bucket,
                    r2_key,
                    ExtraArgs={'ContentType': ct},
                )
                uploaded += 1
                if uploaded % 10 == 0:
                    self.stdout.write(f"   تم رفع {uploaded} ملف...")
            except Exception as e:
                errors += 1
                if errors <= 5:
                    self.stderr.write(f"   ERR {r2_key}: {e}")

        self.stdout.write(f"\n{'[DRY RUN] ' if dry_run else ''}النتيجة:")
        self.stdout.write(f"   رُفع: {uploaded}")
        self.stdout.write(f"   موجود مسبقاً: {skipped}")
        self.stdout.write(f"   أخطاء: {errors}")
