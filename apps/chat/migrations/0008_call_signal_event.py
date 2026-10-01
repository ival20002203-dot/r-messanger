from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies=[("chat","0007_polls_scheduled_posts"),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.CreateModel(
            name="CallSignalEvent",
            fields=[
                ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
                ("call_id",models.CharField(db_index=True,max_length=96)),
                ("event_type",models.CharField(choices=[("call_offer","Offer"),("call_answer","Answer"),("call_ice","ICE"),("call_end","End"),("call_reject","Reject"),("call_busy","Busy")],db_index=True,max_length=16)),
                ("payload",models.JSONField(blank=True,default=dict)),
                ("consumed_at",models.DateTimeField(blank=True,db_index=True,null=True)),
                ("created_at",models.DateTimeField(auto_now_add=True,db_index=True)),
                ("conversation",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="call_signals",to="chat.conversation")),
                ("recipient",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="incoming_call_signals",to=settings.AUTH_USER_MODEL)),
                ("sender",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="outgoing_call_signals",to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering":["id"]},
        ),
        migrations.AddIndex(model_name="callsignalevent",index=models.Index(fields=["recipient","consumed_at","id"],name="chat_callsi_recipie_585011_idx")),
        migrations.AddIndex(model_name="callsignalevent",index=models.Index(fields=["call_id","created_at"],name="chat_callsi_call_id_b67e24_idx")),
    ]
