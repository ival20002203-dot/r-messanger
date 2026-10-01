from django.conf import settings
from django.db import models

class AttachmentScanJob(models.Model):
    class Status(models.TextChoices):
        QUEUED="queued","В очереди"
        PROCESSING="processing","Обработка"
        DONE="done","Готово"
        ERROR="error","Ошибка"
    attachment=models.OneToOneField("chat.Attachment",on_delete=models.CASCADE,related_name="security_job")
    status=models.CharField(max_length=12,choices=Status.choices,default=Status.QUEUED,db_index=True)
    attempts=models.PositiveSmallIntegerField(default=0)
    last_error=models.TextField(blank=True)
    queued_at=models.DateTimeField(auto_now_add=True,db_index=True)
    started_at=models.DateTimeField(null=True,blank=True)
    finished_at=models.DateTimeField(null=True,blank=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:ordering=["queued_at"]

class DLPCase(models.Model):
    class Source(models.TextChoices):
        MESSAGE="message","Сообщение"
        ATTACHMENT="attachment","Вложение"
    class Severity(models.TextChoices):
        LOW="low","Низкий"
        MEDIUM="medium","Средний"
        HIGH="high","Высокий"
        CRITICAL="critical","Критический"
    class Status(models.TextChoices):
        OPEN="open","Открыт"
        REVIEWED="reviewed","Проверен"
        DISMISSED="dismissed","Ложное срабатывание"
    source=models.CharField(max_length=16,choices=Source.choices,db_index=True)
    severity=models.CharField(max_length=12,choices=Severity.choices,default=Severity.MEDIUM,db_index=True)
    status=models.CharField(max_length=12,choices=Status.choices,default=Status.OPEN,db_index=True)
    sender=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL,related_name="dlp_cases")
    conversation=models.ForeignKey("chat.Conversation",null=True,on_delete=models.SET_NULL,related_name="dlp_cases")
    message=models.ForeignKey("chat.Message",null=True,blank=True,on_delete=models.SET_NULL,related_name="dlp_cases")
    attachment=models.ForeignKey("chat.Attachment",null=True,blank=True,on_delete=models.SET_NULL,related_name="dlp_cases")
    rule=models.CharField(max_length=80,db_index=True)
    matches=models.JSONField(default=list,blank=True)
    excerpt=models.TextField(blank=True)
    created_at=models.DateTimeField(auto_now_add=True,db_index=True)
    reviewed_at=models.DateTimeField(null=True,blank=True)
    reviewed_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="dlp_reviews")
    reviewer_note=models.TextField(blank=True)
    class Meta:
        ordering=["-created_at"]
        indexes=[models.Index(fields=["status","severity","created_at"])]

class SecurityIncident(models.Model):
    class Kind(models.TextChoices):
        MALWARE="malware","Malware"
        AUTH="auth","Authentication"
        DEVICE="device","Device"
        DLP="dlp","DLP"
        MODERATION="moderation","Moderation"
    kind=models.CharField(max_length=16,choices=Kind.choices,db_index=True)
    user=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="security_incidents")
    severity=models.CharField(max_length=12,default="medium",db_index=True)
    title=models.CharField(max_length=180)
    details=models.JSONField(default=dict,blank=True)
    created_at=models.DateTimeField(auto_now_add=True,db_index=True)
    resolved_at=models.DateTimeField(null=True,blank=True)
    class Meta:ordering=["-created_at"]
