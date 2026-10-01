from django.db import migrations

def update_policy(apps,schema_editor):
    ClientVersionPolicy=apps.get_model("operations","ClientVersionPolicy")
    for platform in ("windows","android"):
        row,_=ClientVersionPolicy.objects.get_or_create(platform=platform)
        row.latest_version="13.6.0"
        row.enabled=True
        row.save(update_fields=["latest_version","enabled","updated_at"])

class Migration(migrations.Migration):
    dependencies=[("operations","0010_artel_link_v13_5_client_policy")]
    operations=[migrations.RunPython(update_policy,migrations.RunPython.noop)]
