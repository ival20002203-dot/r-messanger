from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("chat", "0009_artel_link_v13_7_history_calls")]
    operations = [
        migrations.AlterField(
            model_name="chatdeletionevent",
            name="scope",
            field=models.CharField(
                choices=[
                    ("self", "Только у себя"),
                    ("peer", "Только у собеседника"),
                    ("everyone", "У всех"),
                ],
                max_length=12,
            ),
        ),
    ]
