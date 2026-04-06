"""
سكربت رفع ملفات uploads المحلية إلى Cloudflare R2
===================================================
تشغيل من جهازك المحلي:
    pip install boto3
    python upload_to_r2.py
    python upload_to_r2.py --dry-run   # معاينة فقط
"""
import argparse
import os
from pathlib import Path

# إعدادات R2
R2_ACCOUNT_ID = '75fa3746ce94b772172774f8c659552a'
R2_ACCESS_KEY = '9d7ad130ae2907d5db1de7b956a0a17d'
R2_SECRET_KEY = 'e1eb90877de8d198c835d7709147b99d68d38a9438d8c1a9bfc9bef21d8113c3'
R2_BUCKET = 'erphr'
R2_ENDPOINT = f'https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com'

# مسار مجلد uploads المحلي
UPLOADS_DIR = Path(__file__).parent / 'media' / 'uploads'

CONTENT_TYPES = {
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


def main():
    parser = argparse.ArgumentParser(description='رفع ملفات media/uploads إلى R2')
    parser.add_argument('--dry-run', action='store_true', help='معاينة بدون رفع فعلي')
    parser.add_argument('--source', type=str, default=str(UPLOADS_DIR), help='مسار مجلد uploads')
    args = parser.parse_args()

    try:
        import boto3
    except ImportError:
        print("❌  يجب تثبيت boto3 أولاً:")
        print("    pip install boto3")
        return

    source = Path(args.source)
    if not source.exists():
        print(f"❌  المجلد غير موجود: {source}")
        return

    # جمع الملفات
    files = [f for f in source.rglob('*') if f.is_file() and f.name != '.gitkeep']
    print(f"📁  عدد الملفات: {len(files)}")
    print(f"📂  المصدر: {source}")
    print(f"☁️   الهدف: {R2_BUCKET}/media/uploads/")
    print()

    if not files:
        print("لا توجد ملفات للرفع!")
        return

    if args.dry_run:
        print("🔍  وضع المعاينة (dry-run):\n")
        for f in files:
            rel = f.relative_to(source)
            print(f"   → media/uploads/{rel}")
        print(f"\n✅  سيتم رفع {len(files)} ملف")
        return

    # إنشاء S3 client
    s3 = boto3.client(
        's3',
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
        region_name='auto',
    )

    uploaded = 0
    skipped = 0
    errors = 0

    for f in files:
        rel = f.relative_to(source)
        r2_key = f"media/uploads/{rel}".replace('\\', '/')

        try:
            # تحقق إذا الملف موجود مسبقاً
            try:
                s3.head_object(Bucket=R2_BUCKET, Key=r2_key)
                skipped += 1
                print(f"   ⏭️  موجود: {r2_key}")
                continue
            except s3.exceptions.ClientError:
                pass

            # رفع
            ext = f.suffix.lower()
            ct = CONTENT_TYPES.get(ext, 'application/octet-stream')
            s3.upload_file(str(f), R2_BUCKET, r2_key, ExtraArgs={'ContentType': ct})
            uploaded += 1
            print(f"   ✅  رُفع: {r2_key}")

        except Exception as e:
            errors += 1
            print(f"   ❌  خطأ: {r2_key} → {e}")

    print(f"\n{'='*50}")
    print(f"✅  رُفع: {uploaded}")
    print(f"⏭️   موجود مسبقاً: {skipped}")
    print(f"❌  أخطاء: {errors}")
    print(f"📊  الإجمالي: {uploaded + skipped + errors} من {len(files)}")


if __name__ == '__main__':
    main()
