# Remove the temporary free-text brand/model fields from Device.
# DeviceModel and Device.device_model remain the canonical catalog relationship.
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('fleet', '0010_device_brand_model_name'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='device',
            name='brand',
        ),
        migrations.RemoveField(
            model_name='device',
            name='model_name',
        ),
    ]
