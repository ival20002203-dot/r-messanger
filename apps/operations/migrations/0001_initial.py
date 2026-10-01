from django.conf import settings
from django.db import migrations,models
import django.db.models.deletion
import django.utils.timezone

class Migration(migrations.Migration):
    initial=True
    dependencies=[migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.CreateModel(name="BackupVerification",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("kind",models.CharField(db_index=True,default="restore_test",max_length=40)),
            ("status",models.CharField(choices=[("passed","Успешно"),("failed","Ошибка"),("running","Выполняется")],db_index=True,default="running",max_length=12)),
            ("source_name",models.CharField(blank=True,max_length=255)),("database_ok",models.BooleanField(default=False)),("object_storage_ok",models.BooleanField(default=False)),("private_media_ok",models.BooleanField(default=False)),("summary",models.TextField(blank=True)),("details",models.JSONField(blank=True,default=dict)),("started_at",models.DateTimeField(db_index=True,default=django.utils.timezone.now)),("finished_at",models.DateTimeField(blank=True,null=True)),
            ("created_by",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="backup_verifications",to=settings.AUTH_USER_MODEL)),],options={"ordering":["-started_at"]}),
        migrations.CreateModel(name="ClientVersionPolicy",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("platform",models.CharField(choices=[("windows","Windows"),("macos","macOS"),("linux","Linux"),("android","Android"),("ios","iOS")],max_length=16,unique=True)),("latest_version",models.CharField(default="7.0.0",max_length=32)),("minimum_version",models.CharField(default="7.0.0",max_length=32)),("update_url",models.URLField(blank=True)),("release_notes",models.TextField(blank=True)),("force_update",models.BooleanField(default=False)),("enabled",models.BooleanField(default=True)),("updated_at",models.DateTimeField(auto_now=True)),
            ("updated_by",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="client_version_policies",to=settings.AUTH_USER_MODEL)),],options={"ordering":["platform"]}),
        migrations.CreateModel(name="RateLimitEvent",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("ip_address",models.GenericIPAddressField(blank=True,db_index=True,null=True)),("category",models.CharField(db_index=True,max_length=40)),("key",models.CharField(blank=True,db_index=True,max_length=190)),("path",models.CharField(blank=True,max_length=255)),("count",models.PositiveIntegerField(default=0)),("limit",models.PositiveIntegerField(default=0)),("blocked",models.BooleanField(db_index=True,default=True)),("details",models.JSONField(blank=True,default=dict)),("created_at",models.DateTimeField(auto_now_add=True,db_index=True)),
            ("user",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="rate_limit_events",to=settings.AUTH_USER_MODEL)),],options={"ordering":["-created_at"],"indexes":[models.Index(fields=["category","created_at"],name="operations__categor_26fe7a_idx"),models.Index(fields=["user","created_at"],name="operations__user_id_a6c990_idx")]}),
        migrations.CreateModel(name="ScheduledJobHeartbeat",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("worker",models.CharField(max_length=80,unique=True)),("last_seen_at",models.DateTimeField(db_index=True,default=django.utils.timezone.now)),("details",models.JSONField(blank=True,default=dict)),]),
    ]
