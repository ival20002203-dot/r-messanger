from django.db import migrations


def update_policy(apps,schema_editor):
    ClientVersionPolicy=apps.get_model("operations","ClientVersionPolicy")
    row,_=ClientVersionPolicy.objects.get_or_create(platform="windows")
    row.latest_version="13.8.2"
    row.release_notes="Исправлено присутствие: серверное время, несколько окон, отключение без зависшего статуса и резервная работа при недоступном Redis."
    row.enabled=True
    row.save(update_fields=["latest_version","release_notes","enabled","updated_at"])


class Migration(migrations.Migration):
    dependencies=[("operations","0014_artel_link_v13_8_1_client_policy")]
    operations=[migrations.RunPython(update_policy,migrations.RunPython.noop)]
