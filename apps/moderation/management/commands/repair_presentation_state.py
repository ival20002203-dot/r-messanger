from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import User
from apps.chat.models import Attachment
from apps.moderation.models import ModerationScanJob
from apps.moderation.services import queue_attachment_scan, queue_avatar_scan
from apps.securitycenter.models import AttachmentScanJob
from apps.securitycenter.services import queue_attachment_security_scan


class Command(BaseCommand):
    help = "Repair/requeue R-Mes presentation queues without deleting user data."

    def handle(self, *args, **options):
        stale = timezone.now() - timedelta(minutes=5)

        # Antivirus: retry failed/stale scans and create jobs for pending attachments.
        sec_reset = 0
        for job in AttachmentScanJob.objects.select_related("attachment").filter(status__in=[
            AttachmentScanJob.Status.ERROR, AttachmentScanJob.Status.PROCESSING
        ]):
            if job.status == AttachmentScanJob.Status.PROCESSING and job.updated_at >= stale:
                continue
            a = job.attachment
            a.scan_status = "pending"
            a.scan_signature = ""
            a.save(update_fields=["scan_status", "scan_signature"])
            queue_attachment_security_scan(a, force=True)
            sec_reset += 1

        sec_created = 0
        for a in Attachment.objects.filter(scan_status__in=["pending", "error"]).iterator(chunk_size=200):
            if not AttachmentScanJob.objects.filter(attachment=a).exists():
                queue_attachment_security_scan(a, force=True)
                sec_created += 1

        # Moderation: old .env files from early test builds often had moderation disabled.
        # Once it is enabled, requeue failed/stale jobs and create missing image/video jobs.
        mod_reset = 0
        mod_created = 0
        if getattr(settings, "CONTENT_MODERATION_ENABLED", False) and getattr(settings, "CONTENT_MODERATION_MEDIA_ENABLED", False):
            for job in ModerationScanJob.objects.filter(status__in=[
                ModerationScanJob.Status.ERROR, ModerationScanJob.Status.PROCESSING
            ]):
                if job.status == ModerationScanJob.Status.PROCESSING and job.updated_at >= stale:
                    continue
                job.status = ModerationScanJob.Status.QUEUED
                job.attempts = 0
                job.last_error = ""
                job.started_at = None
                job.finished_at = None
                job.save(update_fields=["status", "attempts", "last_error", "started_at", "finished_at", "updated_at"])
                mod_reset += 1

            media_ext = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".mp4", ".mov", ".mkv", ".avi", ".webm")
            for a in Attachment.objects.select_related("message").iterator(chunk_size=200):
                ct = (a.content_type or "").lower()
                name = (a.original_name or "").lower()
                if not (ct.startswith("image/") or ct.startswith("video/") or name.endswith(media_ext)):
                    continue
                if not ModerationScanJob.objects.filter(attachment=a).exists():
                    if queue_attachment_scan(a):
                        mod_created += 1

            # Existing avatars also get a chance to enter the review queue.
            for user in User.objects.exclude(avatar="").exclude(avatar__isnull=True).iterator(chunk_size=200):
                if not ModerationScanJob.objects.filter(avatar_user=user).exists():
                    if queue_avatar_scan(user):
                        mod_created += 1

        self.stdout.write(self.style.SUCCESS(
            f"repair complete: security reset={sec_reset}, security created={sec_created}, "
            f"moderation reset={mod_reset}, moderation created={mod_created}"
        ))
