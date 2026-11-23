from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('fleet', '0007_open_device_period_constraints'),
    ]

    operations = [
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
