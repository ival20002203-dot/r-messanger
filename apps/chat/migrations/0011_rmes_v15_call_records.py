from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import apps.chat.models

class Migration(migrations.Migration):
    dependencies=[('chat','0010_artel_link_v13_8_delete_scope'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.CreateModel(
            name='CallRecord',
            fields=[
                ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
                ('call_id',models.CharField(db_index=True,max_length=96,unique=True)),
                ('status',models.CharField(choices=[('ringing','Вызов'),('connected','Соединён'),('ended','Завершён'),('rejected','Отклонён'),('missed','Пропущен'),('busy','Занято'),('failed','Ошибка')],db_index=True,default='ringing',max_length=16)),
                ('started_at',models.DateTimeField(db_index=True,default=django.utils.timezone.now)),
                ('connected_at',models.DateTimeField(blank=True,null=True)),
                ('ended_at',models.DateTimeField(blank=True,db_index=True,null=True)),
                ('duration_seconds',models.PositiveIntegerField(default=0)),
                ('end_reason',models.CharField(blank=True,max_length=80)),
                ('recording',models.FileField(blank=True,upload_to=apps.chat.models.call_recording_path)),
                ('recording_content_type',models.CharField(blank=True,max_length=120)),
                ('recording_size',models.BigIntegerField(default=0)),
                ('recording_sha256',models.CharField(blank=True,max_length=64)),
                ('recording_uploaded_at',models.DateTimeField(blank=True,null=True)),
                ('admin_only',models.BooleanField(default=True)),
                ('created_at',models.DateTimeField(auto_now_add=True)),
                ('updated_at',models.DateTimeField(auto_now=True)),
                ('callee',models.ForeignKey(null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='calls_received',to=settings.AUTH_USER_MODEL)),
                ('caller',models.ForeignKey(null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='calls_started',to=settings.AUTH_USER_MODEL)),
                ('conversation',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='call_records',to='chat.conversation')),
            ],
            options={'ordering':['-started_at']},
        ),
        migrations.AddIndex(model_name='callrecord',index=models.Index(fields=['status','started_at'],name='chat_callre_status_313f13_idx')),
        migrations.AddIndex(model_name='callrecord',index=models.Index(fields=['caller','started_at'],name='chat_callre_caller__cf8b09_idx')),
        migrations.AddIndex(model_name='callrecord',index=models.Index(fields=['callee','started_at'],name='chat_callre_callee__785286_idx')),
    ]
