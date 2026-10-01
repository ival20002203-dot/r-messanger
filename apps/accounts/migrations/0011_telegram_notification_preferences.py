from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0010_artel_link_app_lock")]
    operations = [
        migrations.AddField(model_name="userpreference", name="show_sender_name", field=models.BooleanField(default=True)),
        migrations.AddField(model_name="userpreference", name="notify_direct_chats", field=models.BooleanField(default=True)),
        migrations.AddField(model_name="userpreference", name="notify_groups", field=models.BooleanField(default=True)),
        migrations.AddField(model_name="userpreference", name="notify_channels", field=models.BooleanField(default=True)),
        migrations.AddField(model_name="userpreference", name="suppress_active_chat_notifications", field=models.BooleanField(default=True)),
    ]
