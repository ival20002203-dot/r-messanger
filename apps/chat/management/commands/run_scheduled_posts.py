import time
from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand
from apps.chat.services import process_due_scheduled_post

class Command(BaseCommand):
    help="Send due R-Mes channel scheduled posts"
    def handle(self,*args,**kwargs):
        sleep=max(.5,float(getattr(settings,"SCHEDULED_POST_WORKER_SLEEP",2.0)))
        self.stdout.write(self.style.SUCCESS("R-Mes scheduled-post worker started"))
        while True:
            try:
                cache.set("localgram:scheduler_worker:alive","1",90)
                row=process_due_scheduled_post()
            except Exception as exc:
                self.stderr.write(f"scheduled-post worker retry: {exc}");time.sleep(max(2,sleep));continue
            if not row:time.sleep(sleep)
