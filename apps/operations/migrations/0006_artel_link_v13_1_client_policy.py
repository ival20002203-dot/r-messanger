from django.db import migrations


def forward(apps, schema_editor):
    ClientVersionPolicy=apps.get_model("operations","ClientVersionPolicy")
    ClientVersionPolicy.objects.update_or_create(
        platform="windows",
        defaults={
            "latest_version":"13.1.0",
            "minimum_version":"12.0.0",
            "release_notes":"Уведомления как в Telegram: приватность, категории чатов и надёжный статус обновления.",
            "enabled":True,
        },
    )


class Migration(migrations.Migration):
    dependencies=[("operations","0005_artel_link_v13_client_policy")]
    operations=[migrations.RunPython(forward,migrations.RunPython.noop)]
