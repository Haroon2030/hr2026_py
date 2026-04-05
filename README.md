# نظام الموارد البشرية - HR Pro (Django Edition)
# دليل التثبيت والتشغيل الكامل

## 📋 نظرة عامة

هذا المشروع هو نقل كامل لنظام الموارد البشرية من PHP/MySQL إلى Django مع إدارة كاملة عبر Django Admin.

### الوحدات المتاحة:
| الوحدة | الوصف |
|--------|-------|
| 👥 المستخدمون | إدارة المستخدمين والأدوار والصلاحيات |
| 📁 ملفات الموظفين | إضافة/تعديل/حذف بيانات الموظفين |
| 💰 طلبات السلف | إدارة الطلبات المالية |
| 📝 الإفادات والإجازات | إدارة الإجازات مع رصيد الإجازات |
| ⚠️ المخالفات | تسجيل المخالفات الإدارية |
| 🚪 إنهاء الخدمات | إنهاء خدمات الموظفين |
| 🏥 التأمين الطبي | إدارة التأمينات الطبية |
| 🩺 الأعذار الطبية | إدارة الأعذار الطبية |
| 💵 تعديلات الرواتب | تعديل رواتب الموظفين مع حساب تلقائي |
| 🔄 طلبات النقل | نقل الموظفين بين الفروع/الأقسام |
| ⏰ سجلات الحضور | تسجيل الحضور والانصراف بالدفعات |
| 📨 رسائل النظام | بث رسائل لجميع المستخدمين |
| 🔔 الإشعارات | إشعارات فردية لكل مستخدم |
| 📋 سجل النشاطات | تتبع كامل لجميع العمليات |

### سلسلة الاعتمادات:
```
1. مدير الفرع → 2. مدير الإدارة → 3. المدير العام
```

---

## 🔧 المتطلبات

- Python 3.10+
- MySQL 8.0+ أو MariaDB 10.6+
- pip (مدير حزم Python)

---

## 📦 خطوات التثبيت

### 1. إنشاء البيئة الافتراضية

```bash
cd django_hr
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 2. تثبيت المتطلبات

```bash
pip install -r requirements.txt
```

### 3. إعداد ملف البيئة

```bash
# نسخ ملف الإعدادات
cp .env.example .env

# تحرير الملف وتعديل الإعدادات
# nano .env   (Linux)
# notepad .env (Windows)
```

**تعديل الإعدادات في `.env`:**
```ini
# قاعدة بيانات Django الجديدة
DB_HOST=localhost
DB_NAME=hr_django
DB_USER=root
DB_PASSWORD=your_password

# قاعدة بيانات PHP القديمة (لنقل البيانات)
OLD_DB_HOST=localhost
OLD_DB_NAME=hr_system
OLD_DB_USER=root
OLD_DB_PASSWORD=your_password

# مفتاح الأمان (غيّره لقيمة عشوائية)
SECRET_KEY=your-very-long-random-secret-key-here

# بيئة الإنتاج
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com
```

### 4. إنشاء قاعدة البيانات

```sql
-- في MySQL
CREATE DATABASE hr_django CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 5. تشغيل التهجيرات (Migrations)

```bash
python manage.py makemigrations hr
python manage.py migrate
```

### 6. إنشاء مدير النظام

```bash
# الطريقة السريعة
python manage.py setup_admin

# أو مع تخصيص البيانات
python manage.py setup_admin --username admin --password MySecurePass123 --email admin@company.com --name "مدير النظام"
```

### 7. تشغيل الخادم

```bash
python manage.py runserver
```

ثم افتح المتصفح على: **http://localhost:8000/**

---

## 🔄 نقل البيانات من النظام القديم

### التشغيل التجريبي (بدون حفظ)

```bash
python manage.py migrate_from_php --dry-run
```

### نقل جميع البيانات

```bash
python manage.py migrate_from_php
```

### نقل جدول محدد

```bash
python manage.py migrate_from_php --table users
python manage.py migrate_from_php --table employee_files
python manage.py migrate_from_php --table advance_files
python manage.py migrate_from_php --table statement_files
python manage.py migrate_from_php --table violation_files
python manage.py migrate_from_php --table termination_files
python manage.py migrate_from_php --table medical_insurance
python manage.py migrate_from_php --table medical_excuses
python manage.py migrate_from_php --table salary_adjustments
python manage.py migrate_from_php --table employee_transfer_requests
python manage.py migrate_from_php --table attendance_records
python manage.py migrate_from_php --table system_messages
python manage.py migrate_from_php --table notifications
python manage.py migrate_from_php --table activity_logs
```

### ترتيب النقل الموصى به:
1. `users` (أولاً - تعتمد عليه بقية الجداول)
2. `employee_files`
3. بقية الجداول بأي ترتيب

> ⚠️ **ملاحظة مهمة:** كلمات مرور المستخدمين المنقولين ستكون `changeme123`. يجب تغييرها بعد النقل.

---

## 📊 أوامر مفيدة

### عرض إحصائيات النظام
```bash
python manage.py hr_stats
```

### تنظيف السجلات القديمة
```bash
# تنظيف سجلات أقدم من 90 يوم
python manage.py cleanup_old_records

# تنظيف سجلات أقدم من 30 يوم
python manage.py cleanup_old_records --days 30

# تشغيل تجريبي
python manage.py cleanup_old_records --dry-run
```

### جمع الملفات الثابتة (للإنتاج)
```bash
python manage.py collectstatic
```

### تشغيل الاختبارات
```bash
python manage.py test hr
```

---

## 🖥️ إعداد خادم الإنتاج

### باستخدام Gunicorn + Nginx (Linux)

#### 1. تثبيت Gunicorn
```bash
pip install gunicorn
```

#### 2. إنشاء ملف خدمة systemd
```ini
# /etc/systemd/system/hr_pro.service
[Unit]
Description=HR Pro Django Application
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/django_hr
ExecStart=/path/to/venv/bin/gunicorn hr_project.wsgi:application --bind 127.0.0.1:8000 --workers 3
Restart=always

[Install]
WantedBy=multi-user.target
```

#### 3. تفعيل الخدمة
```bash
sudo systemctl enable hr_pro
sudo systemctl start hr_pro
```

#### 4. إعداد Nginx
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location /static/ {
        alias /path/to/django_hr/staticfiles/;
    }

    location /media/ {
        alias /path/to/django_hr/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 🔐 الأدوار والصلاحيات

| الدور | الوصف | المستوى |
|-------|-------|---------|
| `admin` | مدير النظام | وصول كامل |
| `manager` | المدير العام | اعتماد نهائي |
| `branch_manager` | مدير الفرع | اعتماد أولي |
| `branch` | ممثل الفرع | رفع الطلبات |
| `department_manager` | مدير الإدارة | اعتماد ثانوي |
| `department_employee` | موظف الإدارة | معالجة الطلبات |
| `employee` | موظف | عرض فقط |

### الإدارات:
- `purchasing` - إدارة المشتريات
- `financial` - إدارة المالية
- `technical` - إدارة التقنية
- `data` - إدارة البيانات

---

## 📁 هيكل المشروع

```
django_hr/
├── manage.py                          # أداة إدارة Django
├── requirements.txt                   # المتطلبات
├── .env.example                       # نموذج الإعدادات
├── README.md                          # هذا الملف
│
├── hr_project/                        # إعدادات المشروع
│   ├── settings.py                    # الإعدادات الرئيسية
│   ├── urls.py                        # روابط URL
│   ├── wsgi.py                        # WSGI
│   └── asgi.py                        # ASGI
│
├── hr/                                # تطبيق الموارد البشرية
│   ├── models.py                      # النماذج (14 جدول)
│   ├── admin.py                       # لوحة الإدارة
│   ├── apps.py                        # إعدادات التطبيق
│   ├── signals.py                     # تسجيل النشاطات
│   ├── tests.py                       # الاختبارات
│   ├── management/commands/
│   │   ├── migrate_from_php.py        # نقل البيانات من PHP
│   │   ├── setup_admin.py             # إنشاء المدير
│   │   ├── cleanup_old_records.py     # تنظيف السجلات
│   │   └── hr_stats.py               # إحصائيات النظام
│   └── templatetags/
│       └── hr_tags.py                 # فلاتر القوالب
│
├── locale/                            # ملفات الترجمة
├── media/uploads/                     # الملفات المرفوعة
├── static/                            # الملفات الثابتة
└── logs/                              # سجلات النظام
```

---

## 🔧 ميزات لوحة الإدارة

### لكل نموذج:
- ✅ عرض قائمة مفصلة مع أعمدة مخصصة
- ✅ فلاتر متقدمة (الحالة، الفرع، التاريخ، الاعتمادات)
- ✅ بحث نصي في الحقول المهمة
- ✅ تصدير واستيراد (Excel, CSV)
- ✅ فلتر نطاق التاريخ
- ✅ إجراءات جماعية (اعتماد/رفض/تغيير الحالة)
- ✅ عرض حالة الاعتمادات بألوان مميزة
- ✅ حفظ المستخدم الذي رفع الطلب تلقائياً

### الإجراءات الجماعية:
- ✅ اعتماد مدير الفرع
- ✅ رفض مدير الفرع
- ✅ اعتماد مدير الإدارة
- ✅ رفض مدير الإدارة
- ✅ اعتماد المدير العام
- ✅ رفض المدير العام
- ✅ تحويل إلى "قيد المعالجة"
- ✅ تحديد كمكتمل
- ✅ إعادة تعيين الاعتمادات

### السجلات والتتبع:
- ✅ تسجيل تلقائي لجميع العمليات
- ✅ تتبع تسجيل الدخول والخروج
- ✅ عرض سجل النشاطات (للقراءة فقط)

---

## ⚡ ثوابت النظام

| الثابت | القيمة | الوصف |
|--------|--------|-------|
| أيام الإجازة السنوية | 30 | |
| أيام الإجازة الشهرية | 2.5 | |
| أقصى ترحيل إجازات | 10 | |
| أيام العمل الأسبوعية | 5 | |
| ساعات العمل اليومية | 8 | |
| نسبة التأمينات | 9% | |
| نسبة مكافأة الأداء | 10% | |
| معدل العمل الإضافي | 1.5x | |
| جزاء الغياب / يوم | 100 ر.س | |
| جزاء التأخر / ساعة | 20 ر.س | |
| الحد الأدنى لسن العمل | 18 | |
| سن التقاعد | 60 | |

---

## 📞 الدعم

في حال وجود مشاكل:
1. تحقق من سجلات Django: `logs/django.log`
2. تحقق من إعدادات قاعدة البيانات في `.env`
3. تأكد من تفعيل البيئة الافتراضية
4. شغّل `python manage.py check` للتحقق من الإعدادات
