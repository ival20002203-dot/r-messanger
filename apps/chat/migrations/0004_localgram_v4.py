from django.db import migrations,models

class Migration(migrations.Migration):
    dependencies=[("chat","0003_localgram_v3")]
    operations=[
        migrations.AddField(
            model_name="conversationmember",
            name="chat_theme",
            field=models.CharField(
                choices=[
                    ("default","Классическая"),
                    ("ocean","Ocean"),
                    ("violet","Violet"),
                    ("emerald","Emerald"),
                    ("sunset","Sunset"),
                ],
                default="default",max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="conversationmember",
            name="background_style",
            field=models.CharField(
                choices=[
                    ("classic","Классический"),
                    ("dots","Точки"),
                    ("grid","Сетка"),
                    ("clean","Чистый"),
                ],
                default="classic",max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="conversationmember",
            name="media_previews",
            field=models.BooleanField(default=True),
        ),
    ]
