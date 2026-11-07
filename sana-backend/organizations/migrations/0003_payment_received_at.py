from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('organizations', '0002_installment_ledger'),
    ]

    operations = [
        migrations.RenameField(
            model_name='subscriptionpayment',
            old_name='payment_date',
            new_name='received_at',
        ),
        migrations.AlterField(
            model_name='subscriptionpayment',
            name='received_at',
            field=models.DateField(verbose_name='تاریخ واقعی دریافت وجه'),
        ),
        migrations.AlterModelOptions(
            name='subscriptionpayment',
            options={
                'verbose_name': 'پرداخت',
                'verbose_name_plural': 'پرداخت‌ها',
                'ordering': ['-received_at'],
            },
        ),
    ]
