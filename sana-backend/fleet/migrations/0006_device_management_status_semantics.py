# Normalize legacy device management statuses and introduce the refined lifecycle states.
from django.db import migrations, models


def normalize_legacy_statuses(apps, schema_editor):
    Device = apps.get_model('fleet', 'Device')
    # "sold" was previously used for contract assignment and permanent replacement.
    # Actual sale information remains in lifecycle events / operation metadata.
    Device.objects.filter(management_status='sold').update(management_status='installed')
    # The removed "retired" status is closest to the explicit unusable state.
    Device.objects.filter(management_status='retired').update(management_status='unusable')


class Migration(migrations.Migration):
    dependencies = [
        ('fleet', '0005_alter_devicealertstate_options'),
    ]

    operations = [
        migrations.RunPython(normalize_legacy_statuses, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='device',
            name='management_status',
            field=models.CharField(
                choices=[
                    ('warehouse', 'در انبار'),
                    ('installed', 'نصب شده'),
                    ('active', 'فعال'),
                    ('ready', 'آماده تعیین تکلیف'),
                    ('in_repair', 'در حال تعمیر'),
                    ('faulty', 'خراب'),
                    ('lost', 'گم‌شده'),
                    ('stolen', 'سرقت شده'),
                    ('disconnected', 'قطع سرویس'),
                    ('unusable', 'غیرقابل استفاده'),
                    ('disposed', 'امحاء شده'),
                ],
                default='warehouse',
                max_length=20,
                verbose_name='وضعیت مدیریتی',
            ),
        ),
    ]
