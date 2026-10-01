import json
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.operations.models import BackupVerification

class Command(BaseCommand):
    def add_arguments(self,parser):
        parser.add_argument("--status",choices=["passed","failed","running"],required=True)
        parser.add_argument("--source",default="")
        parser.add_argument("--summary",default="")
        parser.add_argument("--database-ok",action="store_true")
        parser.add_argument("--object-storage-ok",action="store_true")
        parser.add_argument("--private-media-ok",action="store_true")
        parser.add_argument("--details",default="{}")
    def handle(self,*args,**o):
        try:details=json.loads(o["details"] or "{}")
        except Exception:details={"raw":o["details"]}
        row=BackupVerification.objects.create(status=o["status"],source_name=o["source"],summary=o["summary"],database_ok=o["database_ok"],object_storage_ok=o["object_storage_ok"],private_media_ok=o["private_media_ok"],details=details,finished_at=timezone.now() if o["status"]!="running" else None)
        self.stdout.write(self.style.SUCCESS(f"backup verification #{row.pk}: {row.status}"))
