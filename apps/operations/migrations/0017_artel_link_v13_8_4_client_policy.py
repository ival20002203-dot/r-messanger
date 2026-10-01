from django.db import migrations


def set_release(apps, schema_editor):
    Policy=apps.get_model("operations", "ClientVersionPolicy")
    for platform in ("windows", "macos", "linux", "android", "ios"):
        row=Policy.objects.filter(platform=platform).first()
        if row:
            row.latest_version="13.8.4"
            row.save(update_fields=["latest_version", "updated_at"])


class Migration(migrations.Migration):
    dependencies=[("operations", "0016_artel_link_v13_8_3_client_policy")]
    operations=[migrations.RunPython(set_release, migrations.RunPython.noop)]
