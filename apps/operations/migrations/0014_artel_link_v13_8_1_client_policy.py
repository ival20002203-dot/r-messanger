from django.db import migrations


def update_policy(apps,schema_editor):
    ClientVersionPolicy=apps.get_model("operations","ClientVersionPolicy")
    row,_=ClientVersionPolicy.objects.get_or_create(platform="windows")
    row.latest_version="13.8.1"
    row.release_notes="Исправлены серверное время сообщений и статуса в сети, принятие и уведомления аудиозвонков, а контроль 18+ теперь обновляется без перезагрузки и сброса фильтров."
    row.enabled=True
    row.save(update_fields=["latest_version","release_notes","enabled","updated_at"])


class Migration(migrations.Migration):
    dependencies=[("operations","0013_artel_link_v13_8_client_policy")]
    operations=[migrations.RunPython(update_policy,migrations.RunPython.noop)]
