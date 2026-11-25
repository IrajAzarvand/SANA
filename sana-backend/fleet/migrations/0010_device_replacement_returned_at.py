from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('fleet', '0009_device_owner_holder_shape_constraints'),
    ]

    operations = [
        migrations.AddField(
            model_name='devicereplacementrelation',
            name='returned_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='تاریخ بازگشت دستگاه جایگزین موقت',
            ),
        ),
    ]
