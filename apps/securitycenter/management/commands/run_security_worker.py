import time
from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.cache import cache
from apps.securitycenter.services import run_one_job,recover_stale_jobs
class Command(BaseCommand):
    help="Run R-Mes antivirus + DLP attachment worker"
    def handle(self,*args,**kwargs):
        self.stdout.write(self.style.SUCCESS("R-Mes security worker started"))
        sleep=float(getattr(settings,"SECURITY_WORKER_SLEEP",1.0))
        last_recover=0.0
        while True:
            try:
                now=time.monotonic()
                if now-last_recover>30:
                    recover_stale_jobs();last_recover=now
                cache.set("localgram:security_worker:alive","1",90)
                worked=run_one_job()
            except Exception as exc:
                self.stderr.write(f"security worker retry: {exc}");time.sleep(max(2,sleep));continue
            if not worked:time.sleep(sleep)
