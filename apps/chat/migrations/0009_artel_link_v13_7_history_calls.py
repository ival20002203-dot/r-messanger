from django.db import migrations,models


class Migration(migrations.Migration):
    dependencies=[("chat","0008_call_signal_event")]
    operations=[
        migrations.AddField(
            model_name="chatdeletionevent",name="action",
            field=models.CharField(choices=[("delete","Удаление чата"),("clear","Очистка истории")],db_index=True,default="delete",max_length=12),
        ),
        migrations.AddConstraint(
            model_name="callsignalevent",
            constraint=models.UniqueConstraint(condition=~models.Q(event_type="call_ice"),fields=("recipient","sender","call_id","event_type"),name="unique_non_ice_call_signal"),
        ),
    ]
