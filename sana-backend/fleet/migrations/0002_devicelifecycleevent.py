from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ('fleet', '0001_initial'),
        ('organizations', '0001_initial'),
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='device',
            name='management_status',
            field=models.CharField(
                choices=[
                    ('warehouse', 'در انبار'),
                    ('sold', 'فروخته شده'),
                    ('installed', 'نصب شده'),
                    ('active', 'فعال'),
                    ('faulty', 'خراب'),
                    ('lost', 'گمشده'),
                    ('stolen', 'سرقت شده'),
                    ('disconnected', 'قطع سرویس'),
                    ('retired', 'بازنشسته'),
                    ('disposed', 'امحاء شده'),
                ],
                default='warehouse',
                max_length=20,
                verbose_name='وضعیت مدیریتی',
            ),
        ),
        migrations.CreateModel(
            name='DeviceLifecycleEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(
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
                        ('stolen', 'سرقت'),
                        ('retired', 'بازنشستگی'),
                        ('disposed', 'امحاء'),
                    ], max_length=30, verbose_name='نوع رویداد')),
                ('event_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='تاریخ رویداد')),
                ('reason', models.CharField(blank=True, choices=[
                    ('repair', 'تعمیر'),
                    ('replacement', 'تعویض'),
                    ('contract_termination', 'پایان قرارداد'),
                    ('customer_return', 'مرجوعی مشتری'),
                    ('upgrade', 'ارتقاء'),
                    ('defective', 'خرابی'),
                    ('other', 'سایر'),
                ], max_length=30, verbose_name='دلیل')),
                ('description', models.TextField(blank=True, verbose_name='شرح')),
                ('previous_status', models.CharField(blank=True, max_length=20, verbose_name='وضعیت قبلی')),
                ('new_status', models.CharField(blank=True, max_length=20, verbose_name='وضعیت جدید')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('branch', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='device_lifecycle_events', to='organizations.branch', verbose_name='شعبه')),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lifecycle_events', to='fleet.device', verbose_name='دستگاه')),
                ('organization', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='device_lifecycle_events', to='organizations.organization', verbose_name='سازمان')),
                ('performed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='performed_device_lifecycle_events', to='accounts.user', verbose_name='انجام‌دهنده')),
                ('subscription', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='device_lifecycle_events', to='organizations.subscription', verbose_name='قرارداد')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='device_lifecycle_events', to='accounts.user', verbose_name='کاربر')),
                ('vehicle', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='device_lifecycle_events', to='fleet.vehicle', verbose_name='خودرو')),
            ],
            options={
                'verbose_name': 'رویداد چرخه عمر دستگاه',
                'verbose_name_plural': 'رویدادهای چرخه عمر دستگاه',
                'ordering': ['-event_date', '-id'],
            },
        ),
    ]
