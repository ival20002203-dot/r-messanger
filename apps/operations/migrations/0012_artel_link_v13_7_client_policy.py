from django.db import migrations


def update_policy(apps,schema_editor):
    ClientVersionPolicy=apps.get_model("operations","ClientVersionPolicy")
    row,_=ClientVersionPolicy.objects.get_or_create(platform="windows")
    row.latest_version="13.7.0"
    row.release_notes="Исправлены звонки, время присутствия, фото, голосовые, квитанции прочтения, очистка истории и внутреннее автообновление."
    row.enabled=True
    row.save(update_fields=["latest_version","release_notes","enabled","updated_at"])


class Migration(migrations.Migration):
    dependencies=[("operations","0011_artel_link_v13_6_client_policy")]
    operations=[migrations.RunPython(update_policy,migrations.RunPython.noop)]
