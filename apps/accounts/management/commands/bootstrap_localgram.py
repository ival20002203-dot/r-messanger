import os
from django.core.management.base import BaseCommand
from apps.accounts.models import AppSetting,CorporateDomain,User

class Command(BaseCommand):
    help="Bootstrap R-Mes configuration and developer account."
    def handle(self,*args,**opts):
        for d in [x.strip().lower() for x in os.getenv("CORP_EMAIL_DOMAINS","").split(",") if x.strip()]:
            CorporateDomain.objects.get_or_create(domain=d,defaults={"active":True,"registration_enabled":True})
        AppSetting.objects.get_or_create(key="app_name",defaults={"value":"R-Messanger","description":"Название приложения"})
        AppSetting.objects.get_or_create(key="monitoring_notice",defaults={"value":os.getenv("MONITORING_NOTICE","Коммуникации R-Messanger журналируются и защищаются корпоративными политиками."),"description":"Уведомление сотрудникам"})
        email=os.getenv("BOOTSTRAP_ADMIN_EMAIL","").strip().lower()
        password=os.getenv("BOOTSTRAP_ADMIN_PASSWORD","")
        name=os.getenv("BOOTSTRAP_ADMIN_NAME","Infrastructure Admin")
        if email and password:
            u,created=User.objects.get_or_create(email=email,defaults={
                "username":email,"display_name":name,"role":User.Role.DEVELOPER,
                "is_staff":True,"is_superuser":True,"email_verified":True,
            })
            if created:
                u.set_password(password);u.save()
                self.stdout.write(self.style.SUCCESS(f"Admin created: {email}"))
            else:
                changed=False
                for field,val in [("role",User.Role.DEVELOPER),("is_staff",True),("is_superuser",True),("email_verified",True)]:
                    if getattr(u,field)!=val:setattr(u,field,val);changed=True
                if changed:u.save()
