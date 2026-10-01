from django.db import migrations


def forward(apps, schema_editor):
    ClientVersionPolicy=apps.get_model("operations","ClientVersionPolicy")
    ClientVersionPolicy.objects.update_or_create(
        platform="windows",
        defaults={
            "latest_version":"13.3.0",
            "minimum_version":"12.0.0",
            "release_notes":"Presentation 13.3: фирменные уведомления Artel Link, точные счётчики непрочитанных и глобальные WebRTC-звонки с TURN.",
            "enabled":True,
        },
    )


class Migration(migrations.Migration):
    dependencies=[("operations","0007_artel_link_v13_2_client_policy")]
    operations=[migrations.RunPython(forward,migrations.RunPython.noop)]
