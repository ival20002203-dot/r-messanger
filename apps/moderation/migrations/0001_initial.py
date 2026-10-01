import uuid
from django.conf import settings
from django.db import migrations,models
import django.db.models.deletion
import apps.moderation.models

class Migration(migrations.Migration):
    initial=True
    dependencies=[
        ("chat","0004_localgram_v4"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations=[
        migrations.CreateModel(
            name="ModerationCase",
            fields=[
                ("id",models.UUIDField(default=uuid.uuid4,editable=False,primary_key=True,serialize=False)),
                ("kind",models.CharField(choices=[("text","Текст"),("image","Изображение"),("video","Видео"),("file","Файл")],db_index=True,max_length=12)),
                ("status",models.CharField(choices=[("pending","Ожидает проверки"),("confirmed","Нарушение подтверждено"),("dismissed","Ложное срабатывание"),("actioned","Приняты меры")],db_index=True,default="pending",max_length=12)),
                ("detector",models.CharField(blank=True,max_length=80)),
                ("score",models.FloatField(db_index=True,default=0.0)),
                ("labels",models.JSONField(blank=True,default=list)),
                ("reason",models.TextField(blank=True)),
                ("text_snapshot",models.TextField(blank=True)),
                ("evidence_file",models.FileField(blank=True,storage=apps.moderation.models.private_evidence_storage,upload_to=apps.moderation.models.evidence_upload)),
                ("evidence_preview",models.ImageField(blank=True,storage=apps.moderation.models.private_evidence_storage,upload_to=apps.moderation.models.preview_upload)),
                ("evidence_sha256",models.CharField(blank=True,db_index=True,max_length=64)),
                ("created_at",models.DateTimeField(auto_now_add=True,db_index=True)),
                ("reviewed_at",models.DateTimeField(blank=True,null=True)),
                ("reviewer_note",models.TextField(blank=True)),
                ("attachment",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="moderation_cases",to="chat.attachment")),
                ("conversation",models.ForeignKey(null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="moderation_cases",to="chat.conversation")),
                ("message",models.ForeignKey(null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="moderation_cases",to="chat.message")),
                ("reviewed_by",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="moderation_reviews",to=settings.AUTH_USER_MODEL)),
                ("sender",models.ForeignKey(null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="moderation_cases",to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering":["-created_at"]},
        ),
        migrations.CreateModel(
            name="ModerationScanJob",
            fields=[
                ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
                ("source",models.CharField(choices=[("attachment","Вложение"),("avatar","Фото профиля")],db_index=True,default="attachment",max_length=12)),
                ("status",models.CharField(choices=[("queued","В очереди"),("processing","Обработка"),("done","Готово"),("error","Ошибка")],db_index=True,default="queued",max_length=12)),
                ("attempts",models.PositiveSmallIntegerField(default=0)),
                ("last_error",models.TextField(blank=True)),
                ("queued_at",models.DateTimeField(auto_now_add=True,db_index=True)),
                ("started_at",models.DateTimeField(blank=True,null=True)),
                ("finished_at",models.DateTimeField(blank=True,null=True)),
                ("updated_at",models.DateTimeField(auto_now=True)),
                ("attachment",models.OneToOneField(blank=True,null=True,on_delete=django.db.models.deletion.CASCADE,related_name="moderation_job",to="chat.attachment")),
                ("avatar_user",models.OneToOneField(blank=True,null=True,on_delete=django.db.models.deletion.CASCADE,related_name="moderation_avatar_job",to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering":["queued_at"]},
        ),
        migrations.AddIndex(
            model_name="moderationcase",
            index=models.Index(fields=["status","created_at"],name="moderation__status_051d9c_idx"),
        ),
        migrations.AddIndex(
            model_name="moderationcase",
            index=models.Index(fields=["sender","created_at"],name="moderation__sender_2f4d24_idx"),
        ),
    ]
