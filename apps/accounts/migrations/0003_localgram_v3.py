from django.conf import settings
from django.db import migrations,models
import django.db.models.deletion
import apps.accounts.models

class Migration(migrations.Migration):
    dependencies=[
        ("accounts","0002_localgram_v2"),
    ]
    operations=[
        migrations.AddField(
            model_name="user",
            name="avatar",
            field=models.ImageField(blank=True,upload_to=apps.accounts.models.avatar_path),
        ),
        migrations.AddField(
            model_name="user",
            name="handle",
            field=models.CharField(blank=True,max_length=32,null=True,unique=True),
        ),
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("developer","Разработчик"),
                    ("superadmin","Суперадминистратор"),
                    ("infra_admin","Администратор инфраструктуры"),
                    ("moderator","Модератор"),
                    ("auditor","Аудитор"),
                    ("user","Пользователь"),
                ],
                default="user",max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="UserPreference",
            fields=[
                ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
                ("theme",models.CharField(choices=[("dark","Тёмная"),("light","Светлая"),("system","Как в системе")],default="dark",max_length=10)),
                ("desktop_notifications",models.BooleanField(default=True)),
                ("notification_sound",models.BooleanField(default=True)),
                ("show_message_preview",models.BooleanField(default=True)),
                ("enter_to_send",models.BooleanField(default=True)),
                ("compact_mode",models.BooleanField(default=False)),
                ("animated_emoji",models.BooleanField(default=True)),
                ("auto_download_images",models.BooleanField(default=True)),
                ("auto_download_files",models.BooleanField(default=False)),
                ("updated_at",models.DateTimeField(auto_now=True)),
                ("user",models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,related_name="preferences",to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="UserBlock",
            fields=[
                ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
                ("created_at",models.DateTimeField(auto_now_add=True)),
                ("blocked",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="blocked_by_users",to=settings.AUTH_USER_MODEL)),
                ("blocker",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="blocked_users",to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering":["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="userblock",
            constraint=models.UniqueConstraint(fields=("blocker","blocked"),name="unique_user_block"),
        ),
        migrations.AddConstraint(
            model_name="userblock",
            constraint=models.CheckConstraint(condition=~models.Q(blocker=models.F("blocked")),name="prevent_self_block"),
        ),
    ]
