from django.conf import settings
from django.db import migrations,models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies=[
        ("accounts","0003_localgram_v3"),
    ]
    operations=[
        migrations.CreateModel(
            name="ReservedUsername",
            fields=[
                ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
                ("username",models.CharField(db_index=True,max_length=32,unique=True)),
                ("category",models.CharField(
                    choices=[
                        ("system","Системные"),
                        ("official","Официальные / бренд"),
                        ("roles","Должности и подразделения"),
                        ("security","Безопасность"),
                        ("service","Сервисы и инфраструктура"),
                        ("channels","Служебные каналы"),
                        ("popular","Популярные никнеймы"),
                        ("prestige","Короткие / статусные"),
                        ("custom","Пользовательские"),
                    ],
                    db_index=True,default="custom",max_length=16,
                )),
                ("source",models.CharField(
                    choices=[("builtin","Встроенный каталог"),("custom","Добавлен администратором")],
                    default="custom",max_length=10,
                )),
                ("active",models.BooleanField(db_index=True,default=True)),
                ("note",models.CharField(blank=True,max_length=255)),
                ("created_at",models.DateTimeField(auto_now_add=True)),
                ("updated_at",models.DateTimeField(auto_now=True)),
                ("created_by",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="reserved_usernames_created",to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering":["username"]},
        ),
    ]
