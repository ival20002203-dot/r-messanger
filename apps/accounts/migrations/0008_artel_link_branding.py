from django.db import migrations


def apply_branding(apps, schema_editor):
    AppSetting = apps.get_model("accounts", "AppSetting")
    defaults = {
        "app_name": ("Artel Link", "Название приложения"),
        "monitoring_notice": ("Коммуникации Artel Link журналируются и защищаются корпоративными политиками.", "Уведомление сотрудникам"),
    }
    for key, (value, description) in defaults.items():
        row, _ = AppSetting.objects.get_or_create(key=key, defaults={"value": value, "description": description})
        if row.value in ("", "Localgram", "Корпоративные коммуникации журналируются."):
            row.value = value
            if not row.description:
                row.description = description
            row.save(update_fields=["value", "description", "updated_at"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("accounts", "0007_rbac_device_trust")]
    operations = [migrations.RunPython(apply_branding, noop)]
