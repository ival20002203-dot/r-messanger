from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies=[("accounts","0008_artel_link_branding")]
    operations=[
        migrations.AlterField(model_name="userpreference",name="theme",field=models.CharField(choices=[("dark","Ночная"),("light","Дневная"),("tinted","Цветная"),("system","Системная")],default="dark",max_length=10)),
        migrations.AddField(model_name="userpreference",name="accent_color",field=models.CharField(choices=[("artel","Artel Green"),("blue","Синий"),("cyan","Голубой"),("violet","Фиолетовый"),("pink","Розовый"),("orange","Оранжевый"),("red","Красный"),("slate","Графитовый")],default="artel",max_length=12)),
        migrations.AddField(model_name="userpreference",name="chat_background",field=models.CharField(choices=[("artel","Artel"),("clean","Чистый"),("gradient","Градиент"),("dots","Точки")],default="artel",max_length=12)),
        migrations.AddField(model_name="userpreference",name="font_scale",field=models.PositiveSmallIntegerField(default=100)),
        migrations.AddField(model_name="userpreference",name="animations_enabled",field=models.BooleanField(default=True)),
    ]
