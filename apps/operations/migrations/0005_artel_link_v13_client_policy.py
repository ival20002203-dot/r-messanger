from django.db import migrations,models


def forward(apps,schema_editor):
    Policy=apps.get_model("operations","ClientVersionPolicy")
    for platform in ("windows","android","ios","macos","linux"):
        row,_=Policy.objects.get_or_create(platform=platform,defaults={
            "latest_version":"13.0.0","minimum_version":"12.0.0","enabled":True,
        })
        if row.latest_version in {"7.0.0","8.0.0","9.0.0","10.0.0","10.0.1","11.0.0","12.0.0","12.1.0","12.2.0","12.3.0"}:
            row.latest_version="13.0.0"
            if not row.minimum_version or row.minimum_version==row.latest_version:
                row.minimum_version="12.0.0"
            row.save(update_fields=["latest_version","minimum_version","updated_at"])


class Migration(migrations.Migration):
    dependencies=[("operations","0004_artel_link_v12_client_policy")]
    operations=[
        migrations.RunPython(forward,migrations.RunPython.noop),
        migrations.AlterField(model_name="clientversionpolicy",name="latest_version",field=models.CharField(default="13.0.0",max_length=32)),
    ]
