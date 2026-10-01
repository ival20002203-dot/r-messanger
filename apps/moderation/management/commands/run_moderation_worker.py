import time
from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.cache import cache
from apps.moderation.services import run_one_job,recover_stale_jobs

class Command(BaseCommand):
    help="Process R-Mes server-side content moderation jobs."

    def handle(self,*args,**options):
        self.stdout.write(self.style.SUCCESS("R-Mes moderation worker started"))
        sleep=max(0.1,float(getattr(settings,"CONTENT_MODERATION_WORKER_SLEEP",0.25)))
        last_recover=0.0
        while True:
            try:
                now=time.monotonic()
                if now-last_recover>45:
                    recover_stale_jobs();last_recover=now
                cache.set("localgram:moderation_worker:alive","1",90)
                worked=run_one_job()
            except Exception as exc:
                self.stderr.write(f"Moderation worker waiting/retrying: {exc}")
                time.sleep(max(2.0,sleep))
                continue
            if not worked:
                time.sleep(sleep)
