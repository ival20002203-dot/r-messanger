import apps.chat.models
import uuid
from django.conf import settings
from django.db import migrations,models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial=True
    dependencies=[migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.CreateModel(name="Conversation",fields=[
            ("id",models.UUIDField(default=uuid.uuid4,editable=False,primary_key=True,serialize=False)),
            ("kind",models.CharField(choices=[("direct","Личный"),("group","Группа"),("channel","Канал")],default="direct",max_length=10)),
            ("title",models.CharField(blank=True,max_length=180)),("description",models.TextField(blank=True)),
            ("is_archived",models.BooleanField(default=False)),("created_at",models.DateTimeField(auto_now_add=True)),
            ("updated_at",models.DateTimeField(auto_now=True,db_index=True)),
            ("created_by",models.ForeignKey(null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="created_conversations",to=settings.AUTH_USER_MODEL)),
        ],options={"ordering":["-updated_at"]}),
        migrations.CreateModel(name="Message",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("body",models.TextField(blank=True)),("created_at",models.DateTimeField(auto_now_add=True,db_index=True)),
            ("edited_at",models.DateTimeField(blank=True,null=True)),("is_deleted",models.BooleanField(default=False)),
            ("deleted_at",models.DateTimeField(blank=True,null=True)),("deletion_reason",models.CharField(blank=True,max_length=255)),
            ("conversation",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="messages",to="chat.conversation")),
            ("deleted_by",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="+",to=settings.AUTH_USER_MODEL)),
            ("reply_to",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="replies",to="chat.message")),
            ("sender",models.ForeignKey(null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="sent_messages",to=settings.AUTH_USER_MODEL)),
        ],options={"ordering":["created_at"]}),
        migrations.CreateModel(name="ConversationMember",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("role",models.CharField(choices=[("owner","Владелец"),("admin","Администратор"),("member","Участник")],default="member",max_length=10)),
            ("can_write",models.BooleanField(default=True)),("muted",models.BooleanField(default=False)),("joined_at",models.DateTimeField(auto_now_add=True)),
            ("conversation",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="members",to="chat.conversation")),
            ("last_read_message",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="+",to="chat.message")),
            ("user",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="conversation_memberships",to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name="Attachment",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("file",models.FileField(upload_to=apps.chat.models.attachment_path)),("original_name",models.CharField(max_length=255)),
            ("content_type",models.CharField(blank=True,max_length=120)),("size",models.BigIntegerField(default=0)),
            ("sha256",models.CharField(blank=True,max_length=64)),("created_at",models.DateTimeField(auto_now_add=True)),
            ("message",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="attachments",to="chat.message")),
        ]),
        migrations.AddConstraint(model_name="conversationmember",constraint=models.UniqueConstraint(fields=("conversation","user"),name="unique_conversation_member")),
        migrations.AddIndex(model_name="message",index=models.Index(fields=["conversation","created_at"],name="chat_messag_convers_82f431_idx")),
    ]
