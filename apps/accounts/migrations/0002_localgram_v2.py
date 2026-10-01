from django.db import migrations,models

class Migration(migrations.Migration):
    dependencies=[("accounts","0001_initial")]
    operations=[
        migrations.RenameModel(old_name="EmailVerification",new_name="EmailOTP"),
        migrations.AddField(model_name="emailotp",name="purpose",field=models.CharField(choices=[("register","Регистрация"),("login","Вход"),("security","Безопасность")],default="register",max_length=20),preserve_default=False),
        migrations.AddField(model_name="user",name="bio",field=models.CharField(blank=True,max_length=220)),
        migrations.AddField(model_name="user",name="can_make_calls",field=models.BooleanField(default=True)),
        migrations.AddField(model_name="user",name="email_verified",field=models.BooleanField(default=False)),
        migrations.RenameField(model_name="ipaccessrule",old_name="address",new_name="network"),
        migrations.AlterField(model_name="ipaccessrule",name="network",field=models.CharField(help_text="IP или CIDR, например 10.10.0.0/16",max_length=64,unique=True)),
        migrations.AlterField(model_name="apitoken",name="name",field=models.CharField(default="device",max_length=100)),
    ]
