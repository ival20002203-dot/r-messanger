from django.db import migrations


def forward(apps, schema_editor):
    ClientVersionPolicy=apps.get_model("operations","ClientVersionPolicy")
    ClientVersionPolicy.objects.update_or_create(
        platform="windows",
        defaults={
            "latest_version":"13.4.0",
            "minimum_version":"12.0.0",
            "release_notes":"13.4: надёжные вложения, быстрый realtime, фирменные уведомления, исправленные звонки с fallback/TURN и восстановленная 18+ модерация.",
            "enabled":True,
        },
    )


class Migration(migrations.Migration):
    dependencies=[("operations","0008_artel_link_v13_3_client_policy")]
    operations=[migrations.RunPython(forward,migrations.RunPython.noop)]
