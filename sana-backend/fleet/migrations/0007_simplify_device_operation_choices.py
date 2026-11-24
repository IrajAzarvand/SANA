# Keep only the operations exposed by the simplified admin workflow.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('fleet', '0006_device_management_status_semantics'),
    ]

    operations = [
        migrations.AlterField(
            model_name='deviceoperation',
            name='operation_type',
            field=models.CharField(
                choices=[
                    ('return_for_repair', 'بازگشت برای تعمیر'),
                    ('temporary_replacement', 'جایگزینی موقت'),
                    ('permanent_replacement', 'تعویض دائمی'),
                    ('lost', 'گم‌شدن'),
                    ('transfer_customer', 'انتقال به مشتری دیگر'),
                    ('dispose', 'امحاء'),
                ],
                max_length=40,
                verbose_name='نوع عملیات',
            ),
        ),
    ]
