from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies=[("accounts", "0013_artel_link_v13_8_2_presence")]
    operations=[
        migrations.AddField(
            model_name="userpreference",
            name="language",
            field=models.CharField(
                choices=[("ru", "Русский"), ("en", "English"), ("uz", "O‘zbekcha")],
                default="ru",
                max_length=5,
            ),
        ),
    ]
