from django.db import migrations, models


def upgrade_default_policies(apps, schema_editor):
    ClientVersionPolicy=apps.get_model("operations","ClientVersionPolicy")
    for row in ClientVersionPolicy.objects.all():
        changed=[]
        if row.latest_version in {"7.0.0","8.0.0","9.0.0"}:
            row.latest_version="10.0.0";changed.append("latest_version")
        if row.minimum_version in {"7.0.0","8.0.0","9.0.0"}:
            row.minimum_version="10.0.0";changed.append("minimum_version")
        if changed: row.save(update_fields=changed)


class Migration(migrations.Migration):
    dependencies=[("operations","0001_initial")]
    operations=[
        migrations.AlterField(model_name="clientversionpolicy",name="latest_version",field=models.CharField(default="10.0.0",max_length=32)),
        migrations.AlterField(model_name="clientversionpolicy",name="minimum_version",field=models.CharField(default="10.0.0",max_length=32)),
        migrations.RunPython(upgrade_default_policies,migrations.RunPython.noop),
    ]
