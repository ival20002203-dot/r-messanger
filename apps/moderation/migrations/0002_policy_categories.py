from django.db import migrations,models
class Migration(migrations.Migration):
    dependencies=[("moderation","0001_initial")]
    operations=[
        migrations.AddField(model_name="moderationcase",name="policy_category",field=models.CharField(db_index=True,default="sexual",max_length=24)),
        migrations.AddField(model_name="moderationcase",name="risk_points",field=models.PositiveSmallIntegerField(default=0)),
        migrations.AddField(model_name="moderationcase",name="ocr_text",field=models.TextField(blank=True)),
    ]
