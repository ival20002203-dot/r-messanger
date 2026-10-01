from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[('accounts','0015_rmes_presence_privacy_blue_brand')]
    operations=[migrations.AddField(model_name='devicesession',name='push_provider',field=models.CharField(blank=True,max_length=16))]
