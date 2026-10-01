from django.db import migrations, models


def upgrade_default_policies(apps, schema_editor):
    ClientVersionPolicy=apps.get_model("operations","ClientVersionPolicy")
    known={"7.0.0","8.0.0","9.0.0","10.0.0","10.0.1","11.0.0"}
    for row in ClientVersionPolicy.objects.all():
        changed=[]
        if row.latest_version in known:
            row.latest_version="12.0.0";changed.append("latest_version")
        # Do not force an administrator's intentionally older minimum if it was customized.
        if row.minimum_version in known:
            row.minimum_version="12.0.0";changed.append("minimum_version")
        if changed:row.save(update_fields=changed)


class Migration(migrations.Migration):
    dependencies=[("operations","0003_artel_link_v11_client_policy")]
    operations=[
        migrations.AlterField(model_name="clientversionpolicy",name="latest_version",field=models.CharField(default="12.0.0",max_length=32)),
        migrations.AlterField(model_name="clientversionpolicy",name="minimum_version",field=models.CharField(default="12.0.0",max_length=32)),
        migrations.RunPython(upgrade_default_policies,migrations.RunPython.noop),
    ]
