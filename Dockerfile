# ==============================
# Dockerfile for HR Pro Django
# ==============================
FROM python:3.12-slim

# متغيرات البيئة
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8

# مجلد العمل
WORKDIR /app

# تثبيت الحزم المطلوبة للنظام
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    dos2unix \
    curl \
    && rm -rf /var/lib/apt/lists/*

# نسخ ملف المتطلبات وتثبيتها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ كود المشروع
COPY . .

# تحويل line endings وجعل entrypoint قابل للتنفيذ
RUN dos2unix entrypoint.sh && chmod +x entrypoint.sh

# إنشاء مجلدات مطلوبة
RUN mkdir -p logs staticfiles media data

# جمع الملفات الثابتة (مع مفتاح وهمي للبناء فقط)
RUN SECRET_KEY=build-time-key python manage.py collectstatic --noinput

# تعريض المنفذ
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/admin/login/ || exit 1

# أمر التشغيل
ENTRYPOINT ["./entrypoint.sh"]
