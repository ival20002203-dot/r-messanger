from django.conf import settings
from django.db import migrations,models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies=[("accounts","0006_devices_tokens")]
    operations=[
        migrations.CreateModel(name="RoleProfile",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("name",models.CharField(max_length=80,unique=True)),("slug",models.SlugField(max_length=80,unique=True)),("permissions",models.JSONField(blank=True,default=list)),("description",models.CharField(blank=True,max_length=255)),("active",models.BooleanField(default=True)),("created_at",models.DateTimeField(auto_now_add=True)),("updated_at",models.DateTimeField(auto_now=True)),
            ("updated_by",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="role_profiles_updated",to=settings.AUTH_USER_MODEL)),],options={"ordering":["name"]}),
        migrations.AddField(model_name="user",name="custom_role",field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="users",to="accounts.roleprofile")),
        migrations.AddField(model_name="devicesession",name="trust_status",field=models.CharField(choices=[("new","Новое"),("trusted","Доверенное"),("suspicious","Подозрительное"),("blocked","Заблокированное")],db_index=True,default="new",max_length=16)),
        migrations.AddField(model_name="devicesession",name="trust_reason",field=models.CharField(blank=True,max_length=255)),
    ]
