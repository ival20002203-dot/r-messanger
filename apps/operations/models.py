from django.conf import settings
from django.db import models
from django.utils import timezone

class RateLimitEvent(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="rate_limit_events")
    ip_address=models.GenericIPAddressField(null=True,blank=True,db_index=True)
    category=models.CharField(max_length=40,db_index=True)
    key=models.CharField(max_length=190,blank=True,db_index=True)
    path=models.CharField(max_length=255,blank=True)
    count=models.PositiveIntegerField(default=0)
    limit=models.PositiveIntegerField(default=0)
    blocked=models.BooleanField(default=True,db_index=True)
    details=models.JSONField(default=dict,blank=True)
    created_at=models.DateTimeField(auto_now_add=True,db_index=True)
    class Meta:
        ordering=["-created_at"]
        indexes=[models.Index(fields=["category","created_at"]),models.Index(fields=["user","created_at"])]

class BackupVerification(models.Model):
    class Status(models.TextChoices):
        PASSED="passed","Успешно"
        FAILED="failed","Ошибка"
        RUNNING="running","Выполняется"
    kind=models.CharField(max_length=40,default="restore_test",db_index=True)
    status=models.CharField(max_length=12,choices=Status.choices,default=Status.RUNNING,db_index=True)
    source_name=models.CharField(max_length=255,blank=True)
    database_ok=models.BooleanField(default=False)
    object_storage_ok=models.BooleanField(default=False)
    private_media_ok=models.BooleanField(default=False)
    summary=models.TextField(blank=True)
    details=models.JSONField(default=dict,blank=True)
    started_at=models.DateTimeField(default=timezone.now,db_index=True)
    finished_at=models.DateTimeField(null=True,blank=True)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="backup_verifications")
    class Meta: ordering=["-started_at"]

class ClientVersionPolicy(models.Model):
    class Platform(models.TextChoices):
        WINDOWS="windows","Windows"
        MACOS="macos","macOS"
        LINUX="linux","Linux"
        ANDROID="android","Android"
        IOS="ios","iOS"
    platform=models.CharField(max_length=16,choices=Platform.choices,unique=True)
    latest_version=models.CharField(max_length=32,default="13.0.0")
    minimum_version=models.CharField(max_length=32,default="12.0.0")
    update_url=models.URLField(blank=True)
    release_notes=models.TextField(blank=True)
    force_update=models.BooleanField(default=False)
    enabled=models.BooleanField(default=True)
    updated_at=models.DateTimeField(auto_now=True)
    updated_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="client_version_policies")
    class Meta: ordering=["platform"]

class ScheduledJobHeartbeat(models.Model):
    worker=models.CharField(max_length=80,unique=True)
    last_seen_at=models.DateTimeField(default=timezone.now,db_index=True)
    details=models.JSONField(default=dict,blank=True)
