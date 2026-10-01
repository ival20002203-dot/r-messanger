import os
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = "Validate the important R-Mes environment variables."

    def handle(self, *args, **options):
        errors=[]; warnings=[]
        if settings.SECRET_KEY in {"dev-change-me","dev-rmes-change-me",""}: warnings.append("SECRET_KEY is a development value")
        if not settings.DEBUG and not settings.ALLOWED_HOSTS: errors.append("ALLOWED_HOSTS is empty")
        if not settings.DEBUG and not settings.CSRF_TRUSTED_ORIGINS: errors.append("CSRF_TRUSTED_ORIGINS is empty")
        if os.getenv("POSTGRES_HOST") and not os.getenv("POSTGRES_PASSWORD"): errors.append("POSTGRES_PASSWORD is empty")
        if getattr(settings,"USE_S3_STORAGE",False) and not os.getenv("MINIO_ROOT_PASSWORD"): errors.append("MINIO_ROOT_PASSWORD is empty")
        if getattr(settings,"TURN_ENABLED",True) and not os.getenv("TURN_PASSWORD"): warnings.append("TURN_PASSWORD is empty/default")
        self.stdout.write(f"R-Mes {getattr(settings,'APP_VERSION','?')} env check")
        for w in warnings:self.stdout.write(self.style.WARNING("WARN: "+w))
        for e in errors:self.stdout.write(self.style.ERROR("ERROR: "+e))
        if errors: raise CommandError(f"{len(errors)} configuration error(s)")
        self.stdout.write(self.style.SUCCESS("Environment looks usable."))
