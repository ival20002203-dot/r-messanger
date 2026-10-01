from django.db import migrations


def set_release(apps, schema_editor):
    Policy=apps.get_model("operations", "ClientVersionPolicy")
    for platform in ("windows", "macos", "linux", "android", "ios"):
        row=Policy.objects.filter(platform=platform).first()
        if row:
            row.latest_version="13.8.3"
            row.save(update_fields=["latest_version","updated_at"])


class Migration(migrations.Migration):
    dependencies=[("operations", "0015_artel_link_v13_8_2_client_policy")]
    operations=[migrations.RunPython(set_release, migrations.RunPython.noop)]
