import django.db.models.deletion
from django.conf import settings
from django.db import migrations,models
import django.utils.timezone

class Migration(migrations.Migration):
    dependencies=[("accounts","0005_seed_reserved_usernames")]
    operations=[
        migrations.CreateModel(
            name="DeviceSession",
            fields=[
                ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
                ("session_key",models.CharField(blank=True,db_index=True,max_length=64)),
                ("device_id",models.CharField(blank=True,db_index=True,max_length=80)),
                ("device_name",models.CharField(blank=True,max_length=120)),
                ("platform",models.CharField(blank=True,max_length=40)),
                ("browser",models.CharField(blank=True,max_length=80)),
                ("ip_address",models.GenericIPAddressField(blank=True,null=True)),
                ("user_agent",models.TextField(blank=True)),
                ("push_token",models.CharField(blank=True,max_length=512)),
                ("last_seen_at",models.DateTimeField(db_index=True,default=django.utils.timezone.now)),
                ("created_at",models.DateTimeField(auto_now_add=True)),
                ("revoked_at",models.DateTimeField(blank=True,null=True)),
                ("is_current",models.BooleanField(default=False)),
                ("user",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="device_sessions",to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering":["-last_seen_at"]},
        ),
        migrations.CreateModel(
            name="DeviceToken",
            fields=[
                ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
                ("access_hash",models.CharField(db_index=True,max_length=64,unique=True)),
                ("refresh_hash",models.CharField(db_index=True,max_length=64,unique=True)),
                ("access_prefix",models.CharField(db_index=True,max_length=12)),
                ("refresh_prefix",models.CharField(db_index=True,max_length=12)),
                ("access_expires_at",models.DateTimeField(db_index=True)),
                ("refresh_expires_at",models.DateTimeField(db_index=True)),
                ("created_at",models.DateTimeField(auto_now_add=True)),
                ("last_used_at",models.DateTimeField(blank=True,null=True)),
                ("revoked_at",models.DateTimeField(blank=True,null=True)),
                ("device",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.CASCADE,related_name="tokens",to="accounts.devicesession")),
                ("user",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="device_tokens",to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddIndex(model_name="devicesession",index=models.Index(fields=["user","last_seen_at"],name="accounts_de_user_id_871e2f_idx")),
    ]
