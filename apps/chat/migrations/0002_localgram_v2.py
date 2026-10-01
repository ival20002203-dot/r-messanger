from django.conf import settings
from django.db import migrations,models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies=[("chat","0001_initial"),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.AlterField(model_name="conversation",name="kind",field=models.CharField(choices=[("direct","Личный чат"),("group","Группа"),("channel","Канал")],default="direct",max_length=10)),
        migrations.AddField(model_name="conversation",name="only_admins_can_invite",field=models.BooleanField(default=False)),
        migrations.AddField(model_name="conversation",name="only_admins_can_pin",field=models.BooleanField(default=True)),
        migrations.AddField(model_name="conversationmember",name="is_archived",field=models.BooleanField(default=False)),
        migrations.AddField(model_name="conversationmember",name="is_pinned",field=models.BooleanField(default=False)),
        migrations.AddField(model_name="conversationmember",name="muted_until",field=models.DateTimeField(blank=True,null=True)),
        migrations.AddField(model_name="message",name="kind",field=models.CharField(choices=[("text","Текст"),("file","Файл"),("voice","Голосовое"),("system","Системное")],default="text",max_length=12)),
        migrations.AddField(model_name="message",name="forwarded_from",field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="forwards",to="chat.message")),
        migrations.AddField(model_name="conversation",name="pinned_message",field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="+",to="chat.message")),
        migrations.CreateModel(name="MessageRevision",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("old_body",models.TextField()),("new_body",models.TextField()),("created_at",models.DateTimeField(auto_now_add=True)),
            ("editor",models.ForeignKey(null=True,on_delete=django.db.models.deletion.SET_NULL,to=settings.AUTH_USER_MODEL)),
            ("message",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="revisions",to="chat.message")),
        ],options={"ordering":["-created_at"]}),
        migrations.CreateModel(name="Reaction",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("emoji",models.CharField(max_length=16)),("created_at",models.DateTimeField(auto_now_add=True)),
            ("message",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="reactions",to="chat.message")),
            ("user",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.AddConstraint(model_name="reaction",constraint=models.UniqueConstraint(fields=("message","user","emoji"),name="unique_message_user_emoji")),
    ]
