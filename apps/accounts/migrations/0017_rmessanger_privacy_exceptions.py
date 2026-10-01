from django.db import migrations, models
import django.db.models.deletion


def normalize_privacy_and_brand(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    UserPreference = apps.get_model("accounts", "UserPreference")
    AppSetting = apps.get_model("accounts", "AppSetting")
    developer_ids = list(User.objects.filter(role="developer").values_list("id", flat=True))
    UserPreference.objects.exclude(user_id__in=developer_ids).filter(last_seen_privacy="nobody").update(last_seen_privacy="recently")
    AppSetting.objects.update_or_create(key="app_name", defaults={"value":"R-Messanger", "description":"Название приложения"})


class Migration(migrations.Migration):
    dependencies=[("accounts","0016_rmes_v15_push_provider")]
    operations=[
        migrations.CreateModel(
            name="PresencePrivacyException",
            fields=[
                ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
                ("mode",models.CharField(choices=[("always","Всегда показывать"),("except","Не показывать точное время")],max_length=12)),
                ("created_at",models.DateTimeField(auto_now_add=True)),
                ("updated_at",models.DateTimeField(auto_now=True)),
                ("owner",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="presence_privacy_rules",to="accounts.user")),
                ("target",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="presence_visibility_rules",to="accounts.user")),
            ],
            options={"ordering":["target__display_name","target__email"]},
        ),
        migrations.AddConstraint(model_name="presenceprivacyexception",constraint=models.UniqueConstraint(fields=("owner","target"),name="unique_presence_privacy_exception")),
        migrations.AddConstraint(model_name="presenceprivacyexception",constraint=models.CheckConstraint(condition=~models.Q(owner=models.F("target")),name="prevent_self_presence_exception")),
        migrations.RunPython(normalize_privacy_and_brand,migrations.RunPython.noop),
    ]
