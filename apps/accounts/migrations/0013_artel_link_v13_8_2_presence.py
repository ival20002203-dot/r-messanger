from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies=[("accounts","0012_artel_link_v13_8_reserved_assignments")]
    operations=[
        migrations.AddField(
            model_name="user",
            name="presence_active",
            field=models.BooleanField(default=False),
        ),
    ]
