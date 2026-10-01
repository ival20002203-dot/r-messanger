from django.conf import settings
from django.db import migrations,models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies=[("chat","0006_search_index"),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.CreateModel(name="Poll",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("question",models.CharField(max_length=300)),("anonymous",models.BooleanField(default=False)),("multiple_choice",models.BooleanField(default=False)),("closes_at",models.DateTimeField(blank=True,db_index=True,null=True)),("closed_at",models.DateTimeField(blank=True,null=True)),("created_at",models.DateTimeField(auto_now_add=True,db_index=True)),
            ("conversation",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="polls",to="chat.conversation")),("created_by",models.ForeignKey(null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="created_polls",to=settings.AUTH_USER_MODEL)),]),
        migrations.CreateModel(name="ScheduledPost",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("body",models.TextField()),("silent",models.BooleanField(default=False)),("scheduled_for",models.DateTimeField(db_index=True)),("status",models.CharField(choices=[("scheduled","Запланировано"),("sent","Отправлено"),("cancelled","Отменено"),("error","Ошибка")],db_index=True,default="scheduled",max_length=12)),("last_error",models.TextField(blank=True)),("created_at",models.DateTimeField(auto_now_add=True)),("updated_at",models.DateTimeField(auto_now=True)),
            ("conversation",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="scheduled_posts",to="chat.conversation")),("created_by",models.ForeignKey(null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="scheduled_posts",to=settings.AUTH_USER_MODEL)),("sent_message",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="scheduled_source",to="chat.message")),],options={"ordering":["scheduled_for"]}),
        migrations.CreateModel(name="PollOption",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("text",models.CharField(max_length=200)),("position",models.PositiveSmallIntegerField(default=0)),("poll",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="options",to="chat.poll")),],options={"ordering":["position","id"]}),
        migrations.CreateModel(name="PollVote",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("created_at",models.DateTimeField(auto_now_add=True)),("option",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="votes",to="chat.polloption")),("poll",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="votes",to="chat.poll")),("user",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="poll_votes",to=settings.AUTH_USER_MODEL)),],options={"constraints":[models.UniqueConstraint(fields=("option","user"),name="unique_poll_option_user_vote")]}),
        migrations.AddField(model_name="message",name="poll",field=models.OneToOneField(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="message",to="chat.poll")),
        migrations.AlterField(model_name="message",name="kind",field=models.CharField(choices=[("text","Текст"),("file","Файл"),("voice","Голосовое"),("system","Системное"),("sticker","Стикер"),("poll","Опрос")],default="text",max_length=12)),
        migrations.AlterField(model_name="usernotification",name="kind",field=models.CharField(choices=[("mention","Упоминание"),("reply","Ответ"),("reaction","Реакция"),("system","Системное"),("sticker","Стикер"),("poll","Опрос")],db_index=True,default="system",max_length=16)),
    ]
