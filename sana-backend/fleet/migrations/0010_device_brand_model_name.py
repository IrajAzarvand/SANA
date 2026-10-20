# Store the device's commercial brand and model as optional free-text fields.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fleet', '0009_unknowngpsdata'),
    ]

    operations = [
        migrations.AddField(
            model_name='device',
            name='brand',
            field=models.CharField(
                blank=True,
                default='',
                max_length=100,
                verbose_name='برند دستگاه',
            ),
        ),
        migrations.AddField(
            model_name='device',
            name='model_name',
            field=models.CharField(
                blank=True,
                default='',
                max_length=100,
                verbose_name='مدل دستگاه (متنی)',
            ),
        ),
    ]
