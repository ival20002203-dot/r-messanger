from django.db import migrations


def mark_server_release(apps, schema_editor):
    # This is a server/web-client release.  Deliberately do not change
    # ClientVersionPolicy: doing so without a matching native installer would
    # recreate a permanent, unusable "Обновить" banner.  The migration is only
    # an auditable deployment marker.
    return None


class Migration(migrations.Migration):
    dependencies = [("operations", "0018_artel_link_v13_8_5_presence_policy")]
    operations = [migrations.RunPython(mark_server_release, migrations.RunPython.noop)]
