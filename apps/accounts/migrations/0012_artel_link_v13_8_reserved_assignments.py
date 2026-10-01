from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0011_telegram_notification_preferences"),
    ]
    operations = [
        migrations.AddField(model_name="reservedusername",name="assigned_at",field=models.DateTimeField(blank=True,null=True)),
        migrations.AddField(model_name="reservedusername",name="assigned_by",field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="reserved_usernames_assigned",to="accounts.user")),
        migrations.AddField(model_name="reservedusername",name="assigned_to",field=models.OneToOneField(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="reserved_username_assignment",to="accounts.user")),
    ]
