from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('fleet', '0006_device_management_status_semantics'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='devicecustomeraccessperiod',
            constraint=models.UniqueConstraint(
                fields=['device'],
                condition=models.Q(ended_at__isnull=True),
                name='device_access_one_open_period',
            ),
        ),
        migrations.AddConstraint(
            model_name='deviceownershiphistory',
            constraint=models.UniqueConstraint(
                fields=['device'],
                condition=models.Q(ended_at__isnull=True),
                name='device_ownership_one_open_period',
            ),
        ),
    ]
