from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('organizations', '0002_organization_archival'),
    ]

    operations = [
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
