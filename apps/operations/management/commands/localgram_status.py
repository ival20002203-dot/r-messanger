import json
from datetime import timedelta
from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone
from apps.accounts.models import User,LoginEvent,DeviceSession
from apps.chat.models import Message,Attachment
from apps.moderation.models import ModerationCase,ModerationScanJob
from apps.securitycenter.models import DLPCase,AttachmentScanJob

class Command(BaseCommand):
    help="Print R-Mes operational status for Zabbix/CLI"
    def add_arguments(self,parser):
        parser.add_argument("--metric",default="all")
    def handle(self,*args,**o):
        now=timezone.now();db_ok=1
        try:
            with connection.cursor() as c:c.execute("select 1");c.fetchone()
        except Exception:db_ok=0
        data={
            "db_ok":db_ok,"redis_ok":1 if cache.get_or_set("zabbix:probe","1",30)=="1" else 0,
            "users_total":User.objects.count(),"users_online":User.objects.filter(last_seen_at__gte=now-timedelta(seconds=120)).count(),
            "messages_hour":Message.objects.filter(created_at__gte=now-timedelta(hours=1)).count(),
            "attachments_pending":Attachment.objects.filter(scan_status="pending").count(),"attachments_infected":Attachment.objects.filter(scan_status="infected").count(),
            "dlp_open":DLPCase.objects.filter(status="open").count(),"moderation_pending":ModerationCase.objects.filter(status="pending").count(),
            "security_queue":AttachmentScanJob.objects.filter(status__in=["queued","processing"]).count(),"moderation_queue":ModerationScanJob.objects.filter(status__in=["queued","processing"]).count(),
            "worker_security":1 if cache.get("localgram:security_worker:alive") else 0,"worker_moderation":1 if cache.get("localgram:moderation_worker:alive") else 0,"worker_scheduler":1 if cache.get("localgram:scheduler_worker:alive") else 0,
            "failed_login_24h":LoginEvent.objects.filter(successful=False,created_at__gte=now-timedelta(hours=24)).count(),
            "suspicious_devices":DeviceSession.objects.filter(revoked_at__isnull=True,trust_status__in=["suspicious","blocked"]).count(),
        }
        metric=o["metric"]
        if metric!="all":
            if metric not in data:raise SystemExit(f"unknown metric: {metric}")
            self.stdout.write(str(data[metric]));return
        self.stdout.write(json.dumps(data,ensure_ascii=False))
