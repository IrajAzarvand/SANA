from django.db import migrations, models
from django.db.models import Count


def validate_open_period_integrity(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    AccessPeriod = apps.get_model('fleet', 'DeviceCustomerAccessPeriod')
    OwnershipHistory = apps.get_model('fleet', 'DeviceOwnershipHistory')
    invalid_access_dates = AccessPeriod.objects.using(db_alias).filter(ended_at__lt=models.F('started_at')).count()
    invalid_ownership_dates = OwnershipHistory.objects.using(db_alias).filter(ended_at__lt=models.F('started_at')).count()
    duplicate_access = AccessPeriod.objects.using(db_alias).filter(ended_at__isnull=True).values(
        'device_id'
    ).annotate(total=Count('id')).filter(total__gt=1).count()
    duplicate_ownership = OwnershipHistory.objects.using(db_alias).filter(ended_at__isnull=True).values(
        'device_id'
    ).annotate(total=Count('id')).filter(total__gt=1).count()
    if duplicate_access or duplicate_ownership or invalid_access_dates or invalid_ownership_dates:
        raise RuntimeError(
            f'Device history migration blocked: {duplicate_access} devices with multiple open access periods, '
            f'{duplicate_ownership} devices with multiple open ownership records, '
            f'{invalid_access_dates} access periods and {invalid_ownership_dates} ownership periods with reversed dates. '
            'Resolve these records before applying constraints.'
        )


class Migration(migrations.Migration):
    dependencies = [
        ('fleet', '0007_simplify_device_operation_choices'),
    ]

    operations = [
        migrations.RunPython(validate_open_period_integrity, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='devicecustomeraccessperiod',
            constraint=models.CheckConstraint(
                condition=models.Q(ended_at__isnull=True) | models.Q(ended_at__gte=models.F('started_at')),
                name='device_access_valid_dates',
            ),
        ),
        migrations.AddConstraint(
            model_name='devicecustomeraccessperiod',
            constraint=models.UniqueConstraint(
                fields=['device'],
                condition=models.Q(ended_at__isnull=True),
                name='access_one_open_period',
            ),
        ),
        migrations.AddConstraint(
            model_name='deviceownershiphistory',
            constraint=models.UniqueConstraint(
                fields=['device'],
                condition=models.Q(ended_at__isnull=True),
                name='ownership_one_open_period',
            ),
        ),
        migrations.AddConstraint(
            model_name='deviceownershiphistory',
            constraint=models.CheckConstraint(
                condition=models.Q(ended_at__isnull=True) | models.Q(ended_at__gte=models.F('started_at')),
                name='device_ownership_valid_dates',
            ),
        ),
    ]
