from django.conf import settings
from django.db import migrations,models
import django.db.models.deletion
class Migration(migrations.Migration):
    initial=True
    dependencies=[migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.CreateModel(name="AuditEvent",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("action",models.CharField(db_index=True,max_length=120)),
            ("object_type",models.CharField(blank=True,db_index=True,max_length=120)),
            ("object_id",models.CharField(blank=True,db_index=True,max_length=120)),
            ("ip_address",models.GenericIPAddressField(blank=True,null=True)),("user_agent",models.TextField(blank=True)),
            ("metadata",models.JSONField(blank=True,default=dict)),("created_at",models.DateTimeField(auto_now_add=True,db_index=True)),
            ("actor",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,to=settings.AUTH_USER_MODEL)),
        ],options={"ordering":["-created_at"]}),
        migrations.AddIndex(model_name="auditevent",index=models.Index(fields=["action","created_at"],name="audit_action_created_idx")),
        migrations.AddIndex(model_name="auditevent",index=models.Index(fields=["object_type","object_id","created_at"],name="audit_object_created_idx")),
    ]
