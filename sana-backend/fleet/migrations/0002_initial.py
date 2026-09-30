# Squashed development migration for fleet integration and device history.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def backfill_device_history(apps, schema_editor):
    Device = apps.get_model('fleet', 'Device')
    DeviceOwnershipHistory = apps.get_model('fleet', 'DeviceOwnershipHistory')
    DeviceCustomerAccessPeriod = apps.get_model('fleet', 'DeviceCustomerAccessPeriod')

    for device in Device.objects.all().iterator():
        organization_id = device.organization_id or device.current_holder_organization_id
        user_id = device.owner_user_id or device.current_holder_user_id

        if organization_id:
            DeviceOwnershipHistory.objects.get_or_create(
                device_id=device.id,
                ended_at__isnull=True,
                defaults={
                    'organization_id': organization_id,
                    'owner_user_id': None,
                    'reason': 'migration',
                },
            )
        elif user_id:
            DeviceOwnershipHistory.objects.get_or_create(
                device_id=device.id,
                ended_at__isnull=True,
                defaults={
                    'organization_id': None,
                    'owner_user_id': user_id,
                    'reason': 'migration',
                },
            )

        active_link = device.subscription_links.filter(unassigned_at__isnull=True).first()
        if (organization_id or user_id) and device.management_status not in {'warehouse', 'disposed'}:
            DeviceCustomerAccessPeriod.objects.get_or_create(
                device_id=device.id,
                ended_at__isnull=True,
                defaults={
                    'organization_id': organization_id,
                    'user_id': None if organization_id else user_id,
                    'subscription_id': active_link.subscription_id if active_link else None,
                    'branch_id': device.branch_id,
                    'reason': 'migration',
                },
            )


class Migration(migrations.Migration):

    dependencies = [
        ('fleet', '0001_initial'),
        ('organizations', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='device',
            name='branch',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='devices', to='organizations.branch', verbose_name='شعبه'),
        ),
        migrations.AddField(
            model_name='device',
            name='organization',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='devices', to='organizations.organization', verbose_name='سازمان'),
        ),
        migrations.AddField(
            model_name='device',
            name='owner_user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='personal_devices', to=settings.AUTH_USER_MODEL, verbose_name='مالک شخصی'),
        ),
        migrations.AddField(
            model_name='devicelifecycleevent',
            name='branch',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='device_lifecycle_events', to='organizations.branch', verbose_name='شعبه'),
        ),
        migrations.AddField(
            model_name='devicelifecycleevent',
            name='device',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lifecycle_events', to='fleet.device', verbose_name='دستگاه'),
        ),
        migrations.AddField(
            model_name='devicelifecycleevent',
            name='organization',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='device_lifecycle_events', to='organizations.organization', verbose_name='سازمان'),
        ),
        migrations.AddField(
            model_name='devicelifecycleevent',
            name='performed_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='performed_device_lifecycle_events', to=settings.AUTH_USER_MODEL, verbose_name='انجام\u200cدهنده'),
        ),
        migrations.AddField(
            model_name='devicelifecycleevent',
            name='subscription',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='device_lifecycle_events', to='organizations.subscription', verbose_name='قرارداد'),
        ),
        migrations.AddField(
            model_name='devicelifecycleevent',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='device_lifecycle_events', to=settings.AUTH_USER_MODEL, verbose_name='کاربر'),
        ),
        migrations.AddField(
            model_name='device',
            name='device_model',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='devices', to='fleet.devicemodel', verbose_name='مدل دستگاه'),
        ),
        migrations.AddField(
            model_name='driver',
            name='branch',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='drivers', to='organizations.branch', verbose_name='شعبه'),
        ),
        migrations.AddField(
            model_name='driver',
            name='organization',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='drivers', to='organizations.organization', verbose_name='سازمان'),
        ),
        migrations.AddField(
            model_name='vehicle',
            name='branch',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='vehicles', to='organizations.branch', verbose_name='شعبه'),
        ),
        migrations.AddField(
            model_name='vehicle',
            name='organization',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='vehicles', to='organizations.organization', verbose_name='سازمان'),
        ),
        migrations.AddField(
            model_name='vehicle',
            name='owner_user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='personal_vehicles', to=settings.AUTH_USER_MODEL, verbose_name='مالک شخصی'),
        ),
        migrations.AddField(
            model_name='devicelifecycleevent',
            name='vehicle',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='device_lifecycle_events', to='fleet.vehicle', verbose_name='خودرو'),
        ),
        migrations.AddField(
            model_name='device',
            name='vehicle',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='devices', to='fleet.vehicle', verbose_name='خودرو'),
        ),
        migrations.AddField(
            model_name='vehicletype',
            name='organization',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='vehicle_types', to='organizations.organization', verbose_name='سازمان'),
        ),
        migrations.AddField(
            model_name='vehicle',
            name='vehicle_type',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='fleet.vehicletype', verbose_name='نوع خودرو'),
        ),
        migrations.CreateModel(
            name='DeviceReplacementRelation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('replacement_type', models.CharField(choices=[('temporary_repair', 'جایگزینی موقت برای تعمیر'), ('permanent_replacement', 'تعویض دائمی')], max_length=30, verbose_name='نوع جایگزینی')),
                ('replacement_date', models.DateTimeField(default=timezone.now, verbose_name='تاریخ جایگزینی')),
                ('description', models.TextField(blank=True, verbose_name='شرح')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('replacement_device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='replacement_relations_as_replacement', to='fleet.device', verbose_name='دستگاه جایگزین')),
                ('source_device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='replacement_relations_as_source', to='fleet.device', verbose_name='دستگاه قبلی')),
            ],
            options={
                'verbose_name': 'رابطه جایگزینی دستگاه',
                'verbose_name_plural': 'روابط جایگزینی دستگاه‌ها',
                'ordering': ['-replacement_date', '-id'],
            },
        ),
        migrations.AddField(
            model_name='device',
            name='current_holder_organization',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='held_devices',
                to='organizations.organization',
                verbose_name='تحویل‌گیرنده فعلی',
            ),
        ),
        migrations.AddField(
            model_name='device',
            name='current_holder_user',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='held_devices_personal',
                to=settings.AUTH_USER_MODEL,
                verbose_name='تحویل‌گیرنده شخصی',
            ),
        ),
        migrations.CreateModel(
            name='DeviceOperation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('operation_type', models.CharField(
                    choices=[
                        ('return_for_repair', 'بازگشت برای تعمیر'),
                        ('repaired', 'اتمام تعمیر'),
                        ('temporary_replacement', 'جایگزینی موقت'),
                        ('permanent_replacement', 'تعویض دائمی'),
                        ('lost', 'گم‌شدن'),
                        ('stolen', 'سرقت'),
                        ('transfer_customer', 'انتقال به مشتری دیگر'),
                        ('transfer_branch', 'انتقال بین شعب'),
                        ('transfer_vehicle', 'انتقال بین خودروها'),
                        ('retire', 'بازنشستگی'),
                        ('dispose', 'امحاء'),
                    ],
                    max_length=40,
                    verbose_name='نوع عملیات',
                )),
                ('replacement_type', models.CharField(
                    blank=True,
                    choices=[
                        ('temporary_repair', 'جایگزینی موقت برای تعمیر'),
                        ('permanent_replacement', 'تعویض دائمی'),
                    ],
                    max_length=30,
                    verbose_name='نوع جایگزینی',
                )),
                ('reason', models.CharField(blank=True, max_length=30, verbose_name='دلیل')),
                ('description', models.TextField(blank=True, verbose_name='شرح')),
                ('old_status', models.CharField(blank=True, max_length=20, verbose_name='وضعیت قبلی')),
                ('new_status', models.CharField(blank=True, max_length=20, verbose_name='وضعیت جدید')),
                ('performed_at', models.DateTimeField(default=timezone.now, verbose_name='زمان عملیات')),
                ('device', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='operations',
                    to='fleet.device',
                    verbose_name='دستگاه',
                )),
                ('replacement_device', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='replacement_operations',
                    to='fleet.device',
                    verbose_name='دستگاه جایگزین',
                )),
                ('subscription', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='device_operations',
                    to='organizations.subscription',
                    verbose_name='قرارداد',
                )),
                ('target_subscription', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='target_device_operations',
                    to='organizations.subscription',
                    verbose_name='قرارداد مقصد',
                )),
                ('target_organization', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='target_device_operations',
                    to='organizations.organization',
                    verbose_name='سازمان مقصد',
                )),
                ('target_user', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='target_device_operations',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='کاربر مقصد',
                )),
                ('target_branch', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='target_device_operations',
                    to='organizations.branch',
                    verbose_name='شعبه مقصد',
                )),
                ('target_vehicle', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='target_device_operations',
                    to='fleet.vehicle',
                    verbose_name='خودرو مقصد',
                )),
                ('performed_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='device_operations',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='انجام‌دهنده',
                )),
            ],
            options={
                'verbose_name': 'عملیات دستگاه',
                'verbose_name_plural': 'عملیات دستگاه',
                'ordering': ['-performed_at', '-id'],
            },
        ),
        migrations.AddField(
            model_name='devicelifecycleevent',
            name='device_operation',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='lifecycle_events',
                to='fleet.deviceoperation',
                verbose_name='عملیات دستگاه',
            ),
        ),
        migrations.AddField(
            model_name='deviceoperation',
            name='replacement_method',
            field=models.CharField(
                blank=True,
                choices=[
                    ('loaner', 'امانی / موقت'),
                    ('sold', 'فروش به مشتری'),
                    ('free_exchange', 'تعویض بدون هزینه'),
                    ('paid_exchange', 'تعویض با هزینه'),
                    ('warranty', 'تعویض گارانتی'),
                    ('refurbished', 'دستگاه بازسازی‌شده'),
                    ('other', 'سایر'),
                ],
                max_length=30,
                verbose_name='نحوه تجاری جایگزینی',
            ),
        ),
        migrations.AddField(
            model_name='deviceoperation',
            name='repair_return_action',
            field=models.CharField(
                blank=True,
                choices=[
                    ('return_customer_same_vehicle', 'بازگشت به مشتری و نصب روی همان خودرو'),
                    ('return_customer_no_vehicle', 'بازگشت به مشتری بدون نصب'),
                    ('sana_warehouse', 'بازگشت به انبار سانا'),
                    ('customer_spare', 'تحویل به مشتری به عنوان دستگاه یدکی'),
                    ('install_other_vehicle', 'نصب روی خودروی دیگر'),
                    ('transfer_customer', 'انتقال به مشتری دیگر'),
                    ('retire', 'بازنشستگی'),
                    ('dispose', 'امحاء'),
                    ('other', 'سایر'),
                ],
                max_length=40,
                verbose_name='سرنوشت دستگاه پس از تعمیر',
            ),
        ),
        migrations.RenameField(
            model_name='deviceoperation',
            old_name='repair_return_action',
            new_name='outcome_action',
        ),
        migrations.AlterField(
            model_name='device',
            name='management_status',
            field=models.CharField(
                choices=[
                    ('warehouse', 'در انبار'),
                    ('sold', 'فروخته شده'),
                    ('installed', 'نصب شده'),
                    ('active', 'فعال'),
                    ('ready', 'آماده تعیین تکلیف'),
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
                    ('retire', 'بازنشستگی'),
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
                blank=True,
                choices=[
                    ('return_customer_same_vehicle', 'بازگشت به مشتری و نصب روی همان خودرو'),
                    ('return_customer_no_vehicle', 'بازگشت به مشتری بدون نصب'),
                    ('sana_warehouse', 'بازگشت به انبار سانا'),
                    ('customer_spare', 'تحویل به مشتری به عنوان دستگاه یدکی'),
                    ('install_other_vehicle', 'نصب روی خودروی دیگر'),
                    ('transfer_customer', 'انتقال به مشتری دیگر'),
                    ('retire', 'بازنشستگی'),
                    ('dispose', 'امحاء'),
                    ('other', 'سایر'),
                ],
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
                    ('retired', 'بازنشستگی'),
                    ('disposed', 'امحاء'),
                ],
                max_length=30,
                verbose_name='نوع رویداد',
            ),
        ),
        migrations.CreateModel(
            name='DeviceOwnershipHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('started_at', models.DateTimeField(default=timezone.now, verbose_name='شروع مالکیت')),
                ('ended_at', models.DateTimeField(blank=True, null=True, verbose_name='پایان مالکیت')),
                ('reason', models.CharField(blank=True, max_length=40, verbose_name='دلیل تغییر')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ownership_history', to='fleet.device', verbose_name='دستگاه')),
                ('organization', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='device_ownership_history', to='organizations.organization', verbose_name='سازمان مالک')),
                ('owner_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='device_ownership_history', to=settings.AUTH_USER_MODEL, verbose_name='مالک شخصی')),
            ],
            options={
                'verbose_name': 'سابقه مالکیت دستگاه',
                'verbose_name_plural': 'سوابق مالکیت دستگاه‌ها',
                'ordering': ['-started_at', '-id'],
            },
        ),
        migrations.AddConstraint(
            model_name='deviceownershiphistory',
            constraint=models.CheckConstraint(
                condition=(
                    (models.Q(('organization__isnull', False), ('owner_user__isnull', True)))
                    | (models.Q(('organization__isnull', True), ('owner_user__isnull', False)))
                ),
                name='device_ownership_one_customer',
            ),
        ),
        migrations.CreateModel(
            name='DeviceCustomerAccessPeriod',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('started_at', models.DateTimeField(default=timezone.now, verbose_name='شروع دسترسی')),
                ('ended_at', models.DateTimeField(blank=True, null=True, verbose_name='پایان دسترسی')),
                ('reason', models.CharField(blank=True, max_length=40, verbose_name='دلیل')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='customer_access_periods', to='fleet.device', verbose_name='دستگاه')),
                ('organization', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='device_access_periods', to='organizations.organization', verbose_name='سازمان')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='device_access_periods', to=settings.AUTH_USER_MODEL, verbose_name='کاربر شخصی')),
                ('subscription', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='device_access_periods', to='organizations.subscription', verbose_name='قرارداد مرتبط')),
                ('branch', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='device_access_periods', to='organizations.branch', verbose_name='شعبه مرتبط')),
            ],
            options={
                'verbose_name': 'بازه دسترسی مشتری به دستگاه',
                'verbose_name_plural': 'بازه‌های دسترسی مشتری به دستگاه',
                'ordering': ['-started_at', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='devicecustomeraccessperiod',
            index=models.Index(fields=['device', 'started_at', 'ended_at'], name='fleet_device_device_i_3f4a8d_idx'),
        ),
        migrations.AddIndex(
            model_name='devicecustomeraccessperiod',
            index=models.Index(fields=['organization', 'started_at', 'ended_at'], name='fleet_device_organiz_2b2f24_idx'),
        ),
        migrations.AddIndex(
            model_name='devicecustomeraccessperiod',
            index=models.Index(fields=['user', 'started_at', 'ended_at'], name='fleet_device_user_id_2d7d8a_idx'),
        ),
        migrations.AddConstraint(
            model_name='devicecustomeraccessperiod',
            constraint=models.CheckConstraint(
                condition=(
                    (models.Q(('organization__isnull', False), ('user__isnull', True)))
                    | (models.Q(('organization__isnull', True), ('user__isnull', False)))
                ),
                name='device_access_one_customer',
            ),
        ),
        migrations.RunPython(backfill_device_history, migrations.RunPython.noop),
        migrations.RenameIndex(
            model_name='devicecustomeraccessperiod',
            new_name='fleet_devic_device__208b12_idx',
            old_name='fleet_device_device_i_3f4a8d_idx',
        ),
        migrations.RenameIndex(
            model_name='devicecustomeraccessperiod',
            new_name='fleet_devic_organiz_72e79d_idx',
            old_name='fleet_device_organiz_2b2f24_idx',
        ),
        migrations.RenameIndex(
            model_name='devicecustomeraccessperiod',
            new_name='fleet_devic_user_id_4680fb_idx',
            old_name='fleet_device_user_id_2d7d8a_idx',
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
                    ('disposition', 'تعیین تکلیف'),
                    ('stolen', 'سرقت'),
                    ('retired', 'بازنشستگی'),
                    ('disposed', 'امحاء'),
                ],
                max_length=30,
                verbose_name='نوع رویداد',
            ),
        ),
    ]
