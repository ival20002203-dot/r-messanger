import uuid
from pathlib import Path
from django.conf import settings
from django.db import models
from django.core.files.storage import FileSystemStorage

class ModerationEvidenceStorage(FileSystemStorage):
    def __init__(self,*args,**kwargs):
        kwargs.setdefault("location",Path(settings.PRIVATE_MEDIA_ROOT)/"moderation")
        kwargs.setdefault("base_url",None)
        super().__init__(*args,**kwargs)

private_evidence_storage=ModerationEvidenceStorage()

def evidence_upload(instance,filename):
    ext=Path(filename).suffix.lower()[:12] or ".bin"
    return f"evidence/{uuid.uuid4().hex}{ext}"

def preview_upload(instance,filename):
    return f"previews/{uuid.uuid4().hex}.jpg"

class ModerationCase(models.Model):
    class Kind(models.TextChoices):
        TEXT="text","Текст"
        IMAGE="image","Изображение"
        VIDEO="video","Видео"
        FILE="file","Файл"
    class Status(models.TextChoices):
        PENDING="pending","Ожидает проверки"
        CONFIRMED="confirmed","Нарушение подтверждено"
        DISMISSED="dismissed","Ложное срабатывание"
        ACTIONED="actioned","Приняты меры"

    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    kind=models.CharField(max_length=12,choices=Kind.choices,db_index=True)
    status=models.CharField(max_length=12,choices=Status.choices,default=Status.PENDING,db_index=True)
    sender=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL,related_name="moderation_cases")
    conversation=models.ForeignKey("chat.Conversation",null=True,on_delete=models.SET_NULL,related_name="moderation_cases")
    message=models.ForeignKey("chat.Message",null=True,on_delete=models.SET_NULL,related_name="moderation_cases")
    attachment=models.ForeignKey("chat.Attachment",null=True,blank=True,on_delete=models.SET_NULL,related_name="moderation_cases")
    detector=models.CharField(max_length=80,blank=True)
    policy_category=models.CharField(max_length=24,default="sexual",db_index=True)
    risk_points=models.PositiveSmallIntegerField(default=0)
    ocr_text=models.TextField(blank=True)
    score=models.FloatField(default=0.0,db_index=True)
    labels=models.JSONField(default=list,blank=True)
    reason=models.TextField(blank=True)
    text_snapshot=models.TextField(blank=True)
    evidence_file=models.FileField(upload_to=evidence_upload,storage=private_evidence_storage,blank=True)
    evidence_preview=models.ImageField(upload_to=preview_upload,storage=private_evidence_storage,blank=True)
    evidence_sha256=models.CharField(max_length=64,blank=True,db_index=True)
    created_at=models.DateTimeField(auto_now_add=True,db_index=True)
    reviewed_at=models.DateTimeField(null=True,blank=True)
    reviewed_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="moderation_reviews")
    reviewer_note=models.TextField(blank=True)

    class Meta:
        ordering=["-created_at"]
        indexes=[
            models.Index(fields=["status","created_at"]),
            models.Index(fields=["sender","created_at"]),
        ]

class ModerationScanJob(models.Model):
    class Source(models.TextChoices):
        ATTACHMENT="attachment","Вложение"
        AVATAR="avatar","Фото профиля"
    class Status(models.TextChoices):
        QUEUED="queued","В очереди"
        PROCESSING="processing","Обработка"
        DONE="done","Готово"
        ERROR="error","Ошибка"

    source=models.CharField(max_length=12,choices=Source.choices,default=Source.ATTACHMENT,db_index=True)
    attachment=models.OneToOneField("chat.Attachment",null=True,blank=True,on_delete=models.CASCADE,related_name="moderation_job")
    avatar_user=models.OneToOneField(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.CASCADE,related_name="moderation_avatar_job")
    status=models.CharField(max_length=12,choices=Status.choices,default=Status.QUEUED,db_index=True)
    attempts=models.PositiveSmallIntegerField(default=0)
    last_error=models.TextField(blank=True)
    queued_at=models.DateTimeField(auto_now_add=True,db_index=True)
    started_at=models.DateTimeField(null=True,blank=True)
    finished_at=models.DateTimeField(null=True,blank=True)
    updated_at=models.DateTimeField(auto_now=True)

    class Meta:
        ordering=["queued_at"]
