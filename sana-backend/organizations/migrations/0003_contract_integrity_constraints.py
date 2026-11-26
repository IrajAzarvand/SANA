from django.db import migrations, models
from django.db.models import Count, Q


def validate_contract_integrity(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Subscription = apps.get_model('organizations', 'Subscription')
    SubscriptionDevice = apps.get_model('organizations', 'SubscriptionDevice')
    invalid_subscription_dates = Subscription.objects.using(db_alias).filter(end_date__lt=models.F('start_date')).count()
    malformed = Subscription.objects.using(db_alias).exclude(
        Q(customer_type='organization', organization__isnull=False, user__isnull=True)
        | Q(customer_type='personal', organization__isnull=True, user__isnull=False)
    ).count()
    invalid_link_dates = SubscriptionDevice.objects.using(db_alias).filter(end_date__lt=models.F('start_date')).count()
    duplicate_open_links = SubscriptionDevice.objects.filter(unassigned_at__isnull=True).values(
        'device_id'
    ).annotate(total=Count('id')).filter(total__gt=1).count()
    if malformed or invalid_subscription_dates or invalid_link_dates or duplicate_open_links:
        raise RuntimeError(
            f'Contract integrity migration blocked: {malformed} malformed contracts, '
            f'{invalid_subscription_dates} contracts with reversed dates, {invalid_link_dates} links with reversed dates, '
            f'{duplicate_open_links} devices with multiple open contract links. '
            'Resolve these records before applying constraints.'
        )


class Migration(migrations.Migration):
    dependencies = [
        ('organizations', '0002_organization_archival'),
    ]

    operations = [
        migrations.RunPython(validate_contract_integrity, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='subscription',
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(customer_type='organization', organization__isnull=False, user__isnull=True)
                    | models.Q(customer_type='personal', organization__isnull=True, user__isnull=False)
                ),
                name='subscription_customer_shape',
            ),
        ),
        migrations.AddConstraint(
            model_name='subscription',
            constraint=models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F('start_date')),
                name='subscription_valid_dates',
            ),
        ),
        migrations.AddConstraint(
            model_name='subscriptiondevice',
            constraint=models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F('start_date')),
                name='sub_device_valid_dates',
            ),
        ),
        migrations.AddConstraint(
            model_name='subscriptiondevice',
            constraint=models.UniqueConstraint(
                fields=('device',),
                condition=models.Q(unassigned_at__isnull=True),
                name='sub_device_one_open_link',
            ),
        ),
    ]
