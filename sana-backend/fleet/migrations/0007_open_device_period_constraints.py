from django.db import migrations, models
from django.db.models import Count


def validate_open_period_integrity(apps, schema_editor):
    AccessPeriod = apps.get_model('fleet', 'DeviceCustomerAccessPeriod')
    OwnershipHistory = apps.get_model('fleet', 'DeviceOwnershipHistory')
    duplicate_access = AccessPeriod.objects.filter(ended_at__isnull=True).values(
        'device_id'
    ).annotate(total=Count('id')).filter(total__gt=1).count()
    duplicate_ownership = OwnershipHistory.objects.filter(ended_at__isnull=True).values(
        'device_id'
    ).annotate(total=Count('id')).filter(total__gt=1).count()
    if duplicate_access or duplicate_ownership:
        raise RuntimeError(
            f'Device history migration blocked: {duplicate_access} devices with multiple open '
            f'access periods, {duplicate_ownership} devices with multiple open ownership records. '
            'Resolve these records before applying constraints.'
        )


class Migration(migrations.Migration):
    dependencies = [
        ('fleet', '0006_device_management_status_semantics'),
    ]

    operations = [
        migrations.RunPython(validate_open_period_integrity, migrations.RunPython.noop),
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
