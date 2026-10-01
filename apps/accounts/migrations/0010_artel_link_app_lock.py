from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0009_artel_link_appearance")]
    operations = [
        migrations.AddField(
            model_name="userpreference",
            name="app_lock_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="userpreference",
            name="app_lock_code_hash",
            field=models.CharField(blank=True, max_length=256),
        ),
        migrations.AddField(
            model_name="userpreference",
            name="app_lock_timeout_minutes",
            field=models.PositiveSmallIntegerField(default=5),
        ),
        migrations.AddField(
            model_name="userpreference",
            name="app_lock_lock_on_start",
            field=models.BooleanField(default=True),
        ),
    ]
