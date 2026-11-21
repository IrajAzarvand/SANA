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
            model_name='deviceoperation',
            name='operation_type',
            field=models.CharField(
                choices=[
                    ('return_for_repair', 'بازگشت برای تعمیر'),
                    ('repaired', 'اتمام تعمیر'),
                    ('found', 'پیدا شدن دستگاه'),
                    ('disposition', 'تعیین تکلیف دستگاه'),
                    ('temporary_replacement', 'جایگزینی موقت'),
                    ('permanent_replacement', 'تعویض دائمی'),
                    ('lost', 'گم‌شدن'),
                    ('stolen', 'سرقت'),
                    ('transfer_customer', 'انتقال به مشتری دیگر'),
                    ('transfer_branch', 'انتقال بین شعب'),
                    ('transfer_vehicle', 'انتقال بین خودروها'),
                    ('retire', 'خارج کردن از چرخه استفاده'),
                    ('dispose', 'امحاء'),
                ],
                max_length=40,
                verbose_name='نوع عملیات',
            ),
        ),
        migrations.AlterField(
            model_name='deviceoperation',
            name='outcome_action',
            field=models.CharField(
                choices=[
                    ('return_customer_same_vehicle', 'بازگشت به مشتری و نصب روی همان خودرو'),
                    ('return_customer_no_vehicle', 'بازگشت به مشتری بدون نصب'),
                    ('sana_warehouse', 'بازگشت به انبار سانا'),
                    ('customer_spare', 'تحویل به مشتری به عنوان دستگاه یدکی'),
                    ('install_other_vehicle', 'نصب روی خودروی دیگر'),
                    ('transfer_customer', 'انتقال به مشتری دیگر'),
                    ('retire', 'خارج کردن از چرخه استفاده'),
                    ('dispose', 'امحاء'),
                    ('other', 'سایر'),
                ],
                blank=True,
                max_length=40,
                verbose_name='تعیین تکلیف دستگاه',
            ),
        ),
        migrations.AlterField(
            model_name='devicelifecycleevent',
            name='event_type',
            field=models.CharField(
                choices=[
                    ('received', 'دریافت در سانا'),
                    ('sold', 'فروش'),
                    ('assigned_to_contract', 'اتصال به قرارداد'),
                    ('removed_from_contract', 'خروج از قرارداد'),
                    ('returned', 'بازگشت به سانا'),
                    ('sent_to_repair', 'ارسال برای تعمیر'),
                    ('repaired', 'اتمام تعمیر'),
                    ('replaced', 'تعویض'),
                    ('transferred', 'انتقال'),
                    ('lost', 'گم‌شدن'),
                    ('found', 'پیدا شدن'),
                    ('disposition', 'تعیین تکلیف'),
                    ('stolen', 'سرقت'),
                    ('retired', 'خروج از چرخه استفاده'),
                    ('disposed', 'امحاء'),
                ],
                max_length=30,
                verbose_name='نوع رویداد',
            ),
        ),
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
                    ('lost', 'گمشده'),
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
