from django.db import migrations


def forward(apps, schema_editor):
    ClientVersionPolicy=apps.get_model("operations","ClientVersionPolicy")
    ClientVersionPolicy.objects.update_or_create(
        platform="windows",
        defaults={
            "latest_version":"13.5.0",
            "minimum_version":"12.0.0",
            "release_notes":"13.5: Telegram-style media/file sending with instant local preview and real upload progress, reliable retry without duplicates, clean attachment bubbles and server-consistent Tashkent time.",
            "enabled":True,
        },
    )


class Migration(migrations.Migration):
    dependencies=[("operations","0009_artel_link_v13_4_client_policy")]
    operations=[migrations.RunPython(forward,migrations.RunPython.noop)]
