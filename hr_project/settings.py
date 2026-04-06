"""
إعدادات مشروع نظام الموارد البشرية - Django
HR Pro Django Project Settings
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# تحميل متغيرات البيئة من ملف .env
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ==============================
# الأمان / Security
# ==============================
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-change-me-in-production')
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 'yes')

# ALLOWED_HOSTS - يدعم * للسماح بالكل
_hosts = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1')
ALLOWED_HOSTS = ['*'] if _hosts == '*' else [h.strip() for h in _hosts.split(',') if h.strip()]

# CSRF Trusted Origins للإنتاج
_csrf_origins = os.getenv('CSRF_TRUSTED_ORIGINS', '')
if _csrf_origins:
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_origins.split(',') if o.strip()]
else:
    # إنشاء تلقائي من ALLOWED_HOSTS
    if ALLOWED_HOSTS and ALLOWED_HOSTS != ['*']:
        CSRF_TRUSTED_ORIGINS = []
        for h in ALLOWED_HOSTS:
            CSRF_TRUSTED_ORIGINS.extend([f'http://{h}', f'https://{h}', f'http://{h}:8080'])
    elif ALLOWED_HOSTS == ['*']:
        CSRF_TRUSTED_ORIGINS = ['http://*', 'https://*']

# ==============================
# التطبيقات المثبتة / Installed Apps
# ==============================
INSTALLED_APPS = [
    'hr_project.admin_config.HRAdminConfig',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # تطبيقات خارجية
    'import_export',
    'rangefilter',
    'storages',

    # تطبيقات HR Pro
    'apps.core',      # النظام الأساسي (النماذج، المستخدمون)
    'apps.requests',  # طلبات الموظفين
    'apps.system',    # إدارة النظام
    'apps.payroll',   # الرواتب والمالية
]

# ==============================
# Middleware
# ==============================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # خدمة الملفات الثابتة
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'hr_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'hr_project.wsgi.application'

# ==============================
# قاعدة البيانات / Database
# ==============================
# اختيار نوع قاعدة البيانات
# sqlite3 | mysql | postgresql
DB_ENGINE = os.getenv('DB_ENGINE', 'sqlite3')

if DB_ENGINE == 'postgresql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'hr_django'),
            'USER': os.getenv('DB_USER', 'postgres'),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
            'OPTIONS': {
                'client_encoding': 'UTF8',
            },
        }
    }
elif DB_ENGINE == 'mysql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.getenv('DB_NAME', 'hr_django'),
            'USER': os.getenv('DB_USER', 'root'),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '3306'),
            'OPTIONS': {
                'charset': 'utf8mb4',
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        },
    }
    # قاعدة البيانات القديمة (PHP) - تُحمَّل فقط عند توفر OLD_DB_NAME
    if os.getenv('OLD_DB_NAME'):
        DATABASES['legacy'] = {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.getenv('OLD_DB_NAME'),
            'USER': os.getenv('OLD_DB_USER', 'root'),
            'PASSWORD': os.getenv('OLD_DB_PASSWORD', ''),
            'HOST': os.getenv('OLD_DB_HOST', 'localhost'),
            'PORT': os.getenv('OLD_DB_PORT', '3306'),
            'OPTIONS': {
                'charset': 'utf8mb4',
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
else:
    # SQLite - يدعم مسار data/ للحفظ المستمر في Docker
    DB_PATH = os.getenv('DB_PATH', BASE_DIR / 'db.sqlite3')
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': DB_PATH,
        }
    }

# ==============================
# التحقق من كلمات المرور / Password Validation
# ==============================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ==============================
# نموذج المستخدم المخصص / Custom User Model
# ==============================
AUTH_USER_MODEL = 'core.User'

# ==============================
# اللغة والتوقيت / Internationalization
# ==============================
LANGUAGE_CODE = os.getenv('LANGUAGE_CODE', 'ar')
TIME_ZONE = os.getenv('TIME_ZONE', 'Asia/Riyadh')
USE_I18N = True
USE_L10N = True
USE_TZ = True
FORMAT_MODULE_PATH = ['hr_project.formats']

LANGUAGES = [
    ('ar', 'العربية'),
    ('en', 'English'),
]

LOCALE_PATHS = [
    BASE_DIR / 'locale',
]

# ==============================
# الملفات الثابتة والوسائط / Static & Media Files
# ==============================
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# WhiteNoise للملفات الثابتة في الإنتاج
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ==============================
# التخزين السحابي Cloudflare R2 / Cloud Storage
# ==============================
# تفعيل R2 فقط إذا كانت بيانات الاعتماد متوفرة
USE_R2_STORAGE = os.getenv('USE_R2_STORAGE', 'False').lower() in ('true', '1', 'yes')

if USE_R2_STORAGE:
    # Cloudflare R2 Settings
    AWS_ACCESS_KEY_ID = os.getenv('R2_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('R2_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = os.getenv('R2_BUCKET_NAME')
    AWS_S3_ENDPOINT_URL = f"https://{os.getenv('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com"
    AWS_S3_REGION_NAME = 'auto'
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = True
    AWS_S3_FILE_OVERWRITE = False
    AWS_S3_SIGNATURE_VERSION = 's3v4'
    AWS_S3_ADDRESSING_STYLE = 'path'  # مطلوب لـ R2
    
    # التخزين الافتراضي للملفات
    STORAGES = {
        'default': {
            'BACKEND': 'storages.backends.s3boto3.S3Boto3Storage',
            'OPTIONS': {
                'location': 'media',
                'addressing_style': 'path',
            },
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    }
    
    # رابط الملفات العام
    R2_PUBLIC_URL = os.getenv('R2_PUBLIC_URL', '')
    if R2_PUBLIC_URL:
        AWS_S3_CUSTOM_DOMAIN = R2_PUBLIC_URL.replace('https://', '').replace('http://', '')
        MEDIA_URL = f'{R2_PUBLIC_URL}/media/'

# ==============================
# المفتاح التلقائي / Default Auto Field
# ==============================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==============================
# إعدادات رفع الملفات / File Upload Settings
# ==============================
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB

# ==============================
# إعدادات الجلسات / Session Settings
# ==============================
SESSION_COOKIE_AGE = 86400  # 24 ساعة
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG

# ==============================
# إعدادات CSRF
# ==============================
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = not DEBUG

# ==============================
# ثوابت نظام الموارد البشرية / HR Constants
# ==============================
HR_CONSTANTS = {
    # أيام الإجازة
    'VACATION_DAYS_PER_YEAR': 30,
    'VACATION_DAYS_PER_MONTH': 2.5,
    'MAX_VACATION_CARRY_FORWARD': 10,
    'MIN_VACATION_DAYS': 1,

    # جدول العمل
    'WORKING_DAYS_PER_WEEK': 5,
    'WORKING_DAYS_PER_MONTH': 26,
    'WORKING_HOURS_PER_DAY': 8,

    # الرواتب - وفق نظام التأمينات الاجتماعية السعودية (المادتان 17 و18)
    'SOCIAL_INSURANCE_RATE_SAUDI': 0.09,      # حصة صاحب العمل للموظف السعودي 9%
    'SOCIAL_INSURANCE_RATE_NON_SAUDI': 0.02,  # حصة صاحب العمل لغير السعودي 2% (تأمين ضد الأخطار المهنية)
    'EMPLOYEE_INSURANCE_CONTRIBUTION': 0.09,  # حصة الموظف السعودي 9%
    'PERFORMANCE_BONUS_RATE': 0.10,
    'OVERTIME_RATE': 1.5,

    # بدلات الرواتب الشهرية
    'HOUSING_ALLOWANCE_RATE': 0.25,       # بدل السكن 25% من الراتب الأساسي
    'TRANSPORT_ALLOWANCE_DEFAULT': 400,   # بدل النقل الافتراضي (ريال)
    'MEAL_ALLOWANCE_DEFAULT': 0,          # بدل الوجبات الافتراضي (ريال)

    # الجزاءات
    'ABSENCE_PENALTY_PER_DAY': 100,
    'LATE_PENALTY_PER_HOUR': 20,

    # التوظيف - وفق نظام العمل السعودي
    'MIN_EMPLOYMENT_AGE': 18,
    'RETIREMENT_AGE_MALE': 65,    # سن تقاعد الرجل - نظام المعاشات السعودي
    'RETIREMENT_AGE_FEMALE': 60,  # سن تقاعد المرأة - نظام المعاشات السعودي

    # أنواع الملفات المسموحة
    'ALLOWED_FILE_TYPES': ['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'xls', 'xlsx'],
    'MAX_FILE_SIZE_MB': 5,
}

# ==============================
# إعدادات AdminDek (واجهة الإدارة) – الثيم محمّل عبر templates/admin/base.html
# ==============================
HR_ADMIN_SETTINGS = {
    "site_title": "نظام الموارد البشرية",
    "site_header": "HR Pro",
    "site_brand": "HR Pro",
    "copyright": "HR Pro System",
}

# ==============================
# إعدادات التسجيل / Logging
# ==============================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'WARNING',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
}

# إنشاء مجلد السجلات تلقائياً
(BASE_DIR / 'logs').mkdir(exist_ok=True)

# ==============================
# إعدادات الأمان للإنتاج / Production Security
# ==============================
if not DEBUG:
    # HTTPS إجباري - يمكن تعطيله عبر متغير البيئة
    SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'False').lower() in ('true', '1', 'yes')
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    
    # Trust X-Forwarded headers from proxy
    USE_X_FORWARDED_HOST = True
    USE_X_FORWARDED_PORT = True
    
    # HSTS - تفعيل بعد التأكد من HTTPS
    if SECURE_SSL_REDIRECT:
        SECURE_HSTS_SECONDS = 31536000  # سنة
        SECURE_HSTS_INCLUDE_SUBDOMAINS = True
        SECURE_HSTS_PRELOAD = True
    
    # أمان الكوكيز
    SESSION_COOKIE_SECURE = SECURE_SSL_REDIRECT
    CSRF_COOKIE_SECURE = SECURE_SSL_REDIRECT
    
    # حماية إضافية
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = 'DENY'
