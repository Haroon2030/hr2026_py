from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from apps.core.models import MedicalInsurance

class Command(BaseCommand):
    help = 'يرسل تنبيهات لانتهاء مستندات وتأمينات الموظفين'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.NOTICE(">> بدء تشغيل التنبيهات الذكية (Smart Reminders)..."))
        
        today = timezone.now().date()
        warning_date = today + timedelta(days=30)
        
        # 1. تنبيهات التأمين الطبي (بافتراض أن التأمين ينتهي بعد سنة من تاريخ الإصدار created_at)
        insurances = MedicalInsurance.objects.filter(status='approved')
        
        expiring_insurances = []
        for ins in insurances:
            # افتراضياً: وثيقة التأمين صالحة لمدة عام كامل من تاريخ إدخالها
            expiry_date = ins.created_at.date() + timedelta(days=365)
            
            # إذا كان التأمين سينتهي خلال 30 يوماً وتاريخ الانتهاء بعد اليوم المستقبلي
            if today <= expiry_date <= warning_date:
                days_left = (expiry_date - today).days
                expiring_insurances.append((ins.employee_name, expiry_date, days_left))

        if expiring_insurances:
            self.stdout.write(self.style.WARNING(f"\n[!] تم العثور على {len(expiring_insurances)} تأمينات طبية توشك على الانتهاء:"))
            for emp_name, expiry, days in expiring_insurances:
                self.stdout.write(f" - الموظف: {emp_name} | تاريخ الانتهاء: {expiry.strftime('%Y-%m-%d')} | متبقي: {days} يوم")
        else:
            self.stdout.write(self.style.SUCCESS("\n[✓] لا توجد تأمينات طبية توشك على الانتهاء خلال 30 يوماً."))
        
        
        self.stdout.write(self.style.SUCCESS("\n>> اكتمل الفحص بنجاح! يمكن جدولة هذا السكربت للعمل يومياً."))
