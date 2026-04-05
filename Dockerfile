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
    && rm -rf /var/lib/apt/lists/*

# نسخ ملف المتطلبات وتثبيتها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ كود المشروع
COPY . .

# جعل entrypoint قابل للتنفيذ
RUN chmod +x entrypoint.sh

# إنشاء مجلدات مطلوبة
RUN mkdir -p logs staticfiles media

# جمع الملفات الثابتة
RUN python manage.py collectstatic --noinput

# تعريض المنفذ
EXPOSE 8000

# أمر التشغيل
ENTRYPOINT ["./entrypoint.sh"]
