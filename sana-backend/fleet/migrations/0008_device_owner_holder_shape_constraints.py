from django.db import migrations, models
from django.db.models import Q


def validate_device_owner_holder_integrity(apps, schema_editor):
    Device = apps.get_model('fleet', 'Device')
    invalid_owner = Device.objects.filter(organization__isnull=False, owner_user__isnull=False).count()
    invalid_holder = Device.objects.filter(
        current_holder_organization__isnull=False,
        current_holder_user__isnull=False,
    ).count()
    if invalid_owner or invalid_holder:
        raise RuntimeError(
            f'Device owner/holder migration blocked: {invalid_owner} devices have two legal owners, '
            f'{invalid_holder} devices have two current holders. Resolve these records before applying constraints.'
        )


class Migration(migrations.Migration):
    dependencies = [
        ('fleet', '0007_open_device_period_constraints'),
    ]

    operations = [
        migrations.RunPython(validate_device_owner_holder_integrity, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='device',
            constraint=models.CheckConstraint(
                condition=(
                    (models.Q(organization__isnull=True) & models.Q(owner_user__isnull=True))
                    | (models.Q(organization__isnull=False) & models.Q(owner_user__isnull=True))
                    | (models.Q(organization__isnull=True) & models.Q(owner_user__isnull=False))
                ),
                name='device_legal_owner_shape',
            ),
        ),
        migrations.AddConstraint(
            model_name='device',
            constraint=models.CheckConstraint(
                condition=(
                    (models.Q(current_holder_organization__isnull=True) & models.Q(current_holder_user__isnull=True))
                    | (models.Q(current_holder_organization__isnull=False) & models.Q(current_holder_user__isnull=True))
                    | (models.Q(current_holder_organization__isnull=True) & models.Q(current_holder_user__isnull=False))
                ),
                name='device_holder_shape',
            ),
        ),
    ]
