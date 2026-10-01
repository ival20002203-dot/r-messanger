from django.db import migrations, models


def migrate_brand_and_preferences(apps, schema_editor):
    UserPreference = apps.get_model("accounts", "UserPreference")
    AppSetting = apps.get_model("accounts", "AppSetting")
    UserPreference.objects.filter(accent_color="artel").update(accent_color="blue")
    UserPreference.objects.filter(chat_background="artel").update(chat_background="rmes")
    AppSetting.objects.update_or_create(key="app_name", defaults={"value":"R-Mes", "description":"Название приложения"})
    AppSetting.objects.update_or_create(
        key="monitoring_notice",
        defaults={"value":"Коммуникации R-Mes журналируются и защищаются корпоративными политиками.", "description":"Уведомление сотрудникам"},
    )


class Migration(migrations.Migration):
    dependencies=[("accounts", "0014_artel_link_language_preferences")]
    operations=[
        migrations.AddField(
            model_name="userpreference",
            name="last_seen_privacy",
            field=models.CharField(
                choices=[("everybody","Точное время"),("recently","Недавно"),("nobody","Скрыто")],
                default="everybody",max_length=12,
            ),
        ),
        migrations.AlterField(
            model_name="userpreference",name="accent_color",
            field=models.CharField(choices=[("blue","Синий"),("cyan","Голубой"),("violet","Фиолетовый"),("pink","Розовый"),("orange","Оранжевый"),("red","Красный"),("slate","Графитовый")],default="blue",max_length=12),
        ),
        migrations.AlterField(
            model_name="userpreference",name="chat_background",
            field=models.CharField(choices=[("rmes","R-Mes Blue"),("clean","Чистый"),("gradient","Градиент"),("dots","Точки")],default="rmes",max_length=12),
        ),
        migrations.RunPython(migrate_brand_and_preferences, migrations.RunPython.noop),
    ]
