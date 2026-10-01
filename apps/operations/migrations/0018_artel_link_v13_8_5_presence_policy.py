from django.db import migrations


def set_release(apps, schema_editor):
    Policy = apps.get_model("operations", "ClientVersionPolicy")
    notes = (
        "Telegram-подобное присутствие: отдельные окна и устройства, "
        "мгновенный online/offline, серверное время последнего посещения и "
        "скрытие времени разработчика от обычных пользователей."
    )
    for platform in ("windows", "macos", "linux", "android", "ios"):
        row = Policy.objects.filter(platform=platform).first()
        if row:
            row.latest_version = "13.8.5"
            row.release_notes = notes
            row.save(update_fields=["latest_version", "release_notes", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [("operations", "0017_artel_link_v13_8_4_client_policy")]
    operations = [migrations.RunPython(set_release, migrations.RunPython.noop)]
