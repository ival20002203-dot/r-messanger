from django.conf import settings
from django.db import migrations,models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies=[
        ("chat","0002_localgram_v2"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations=[
        migrations.AddField(
            model_name="conversationmember",
            name="is_hidden",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="conversationmember",
            name="hidden_before_message_id",
            field=models.BigIntegerField(blank=True,null=True),
        ),
        migrations.AddField(
            model_name="conversationmember",
            name="notifications_enabled",
            field=models.BooleanField(default=True),
        ),
        migrations.CreateModel(
            name="MessageHiddenFor",
            fields=[
                ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
                ("created_at",models.DateTimeField(auto_now_add=True)),
                ("message",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="hidden_for",to="chat.message")),
                ("user",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="hidden_messages",to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="messagehiddenfor",
            constraint=models.UniqueConstraint(fields=("message","user"),name="unique_message_hidden_for"),
        ),
        migrations.CreateModel(
            name="ChatDeletionEvent",
            fields=[
                ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
                ("scope",models.CharField(choices=[("self","Только у себя"),("everyone","У всех")],max_length=12)),
                ("through_message_id",models.BigIntegerField(blank=True,null=True)),
                ("affected_user_ids",models.JSONField(blank=True,default=list)),
                ("protected_developer_ids",models.JSONField(blank=True,default=list)),
                ("created_at",models.DateTimeField(auto_now_add=True,db_index=True)),
                ("actor",models.ForeignKey(null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="chat_deletion_events",to=settings.AUTH_USER_MODEL)),
                ("conversation",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="deletion_events",to="chat.conversation")),
            ],
            options={"ordering":["-created_at"]},
        ),
    ]
