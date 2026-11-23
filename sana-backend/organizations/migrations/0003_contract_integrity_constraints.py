from django.db import migrations, models
from django.db.models import Count, Q


def validate_contract_integrity(apps, schema_editor):
    Subscription = apps.get_model('organizations', 'Subscription')
    SubscriptionDevice = apps.get_model('organizations', 'SubscriptionDevice')
    malformed = Subscription.objects.exclude(
        Q(customer_type='organization', organization__isnull=False, user__isnull=True)
        | Q(customer_type='personal', organization__isnull=True, user__isnull=False)
    ).count()
    duplicate_links = SubscriptionDevice.objects.filter(unassigned_at__isnull=True).values(
        'device_id'
    ).annotate(total=Count('id')).filter(total__gt=1).count()
    if malformed or duplicate_links:
        raise RuntimeError(
            f'Contract integrity migration blocked: {malformed} malformed contracts, '
            f'{duplicate_links} devices with multiple active contract links. '
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
            model_name='subscriptiondevice',
            constraint=models.UniqueConstraint(
                fields=['device'],
                condition=models.Q(unassigned_at__isnull=True),
                name='subscription_device_one_active',
            ),
        ),
    ]
