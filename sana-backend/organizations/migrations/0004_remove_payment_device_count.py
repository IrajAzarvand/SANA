from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('organizations', '0003_payment_received_at'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='subscriptionpayment',
            name='device_count',
        ),
    ]
