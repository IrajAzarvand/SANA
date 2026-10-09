# Allow IMEI-only registration and store the protocol detected by the GPS service.
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('fleet', '0003_drivervehicleassignment'),
    ]

    operations = [
        migrations.AlterField(
            model_name='device',
            name='device_model',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='devices',
                to='fleet.devicemodel',
                verbose_name='مدل دستگاه',
            ),
        ),
        migrations.AddField(
            model_name='device',
            name='protocol',
            field=models.CharField(
                blank=True,
                default='',
                max_length=50,
                verbose_name='پروتکل شناسایی‌شده',
            ),
        ),
    ]
