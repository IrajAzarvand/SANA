# Generated manually after separating the User base table from its organization/branch foreign keys.
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial = True
    dependencies = [('fleet','0001_initial'),('accounts','0001_initial')]
    operations = [
        migrations.CreateModel(name='Organization', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('name', models.CharField(max_length=200, verbose_name='نام سازمان')),('code', models.CharField(max_length=50, unique=True, verbose_name='کد سازمان')),
            ('registration_number', models.CharField(blank=True, max_length=50, verbose_name='شماره ثبت')),('economy_code', models.CharField(blank=True, max_length=50, verbose_name='کد اقتصادی')),
            ('phone', models.CharField(blank=True, max_length=20, verbose_name='تلفن')),('email', models.EmailField(blank=True, max_length=254, verbose_name='ایمیل')),('address', models.TextField(blank=True, verbose_name='آدرس')),('website', models.URLField(blank=True, max_length=200, verbose_name='وبسایت')),('logo', models.ImageField(blank=True, null=True, upload_to='organizations/logos/', verbose_name='لوگو')),
            ('status', models.CharField(choices=[('active','فعال'),('inactive','غیرفعال'),('suspended','تعلیق‌شده')], default='active', max_length=20, verbose_name='وضعیت')),
            ('created_at', models.DateTimeField(auto_now_add=True)),('updated_at', models.DateTimeField(auto_now=True)),
        ], options={'verbose_name':'سازمان','verbose_name_plural':'سازمان‌ها','ordering':['name']}),
        migrations.CreateModel(name='Branch', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),('name', models.CharField(max_length=200, verbose_name='نام شعبه')),('code', models.CharField(max_length=50, verbose_name='کد شعبه')),('phone', models.CharField(blank=True, max_length=20, verbose_name='تلفن')),('address', models.TextField(blank=True, verbose_name='آدرس')),('status', models.CharField(choices=[('active','فعال'),('inactive','غیرفعال')], default='active', max_length=20, verbose_name='وضعیت')),('created_at', models.DateTimeField(auto_now_add=True)),('updated_at', models.DateTimeField(auto_now=True)),
            ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='branches', to='organizations.organization', verbose_name='سازمان')),
        ], options={'verbose_name':'شعبه','verbose_name_plural':'شعبه‌ها','ordering':['organization','name'],'unique_together':{('organization','code')}}),
        migrations.CreateModel(name='Subscription', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),('contract_number', models.CharField(max_length=50, unique=True, verbose_name='شماره قرارداد')),('customer_type', models.CharField(choices=[('organization','سازمانی'),('personal','شخصی')], default='organization', max_length=20, verbose_name='نوع مشتری')),('start_date', models.DateField(verbose_name='تاریخ شروع قرارداد')),('end_date', models.DateField(verbose_name='تاریخ پایان قرارداد')),('price', models.DecimalField(decimal_places=0, default=0, max_digits=15, verbose_name='مبلغ کل (ریال)')),('status', models.CharField(choices=[('active','فعال'),('suspended','تعلیق‌شده'),('expired','منقضی'),('cancelled','لغو‌شده')], default='active', max_length=20, verbose_name='وضعیت')),('notes', models.TextField(blank=True, verbose_name='یادداشت')),('created_at', models.DateTimeField(auto_now_add=True)),('updated_at', models.DateTimeField(auto_now=True)),
            ('organization', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='subscriptions', to='organizations.organization', verbose_name='سازمان')),
            ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='personal_subscriptions', to='accounts.user', verbose_name='کاربر شخصی')),
        ], options={'verbose_name':'قرارداد','verbose_name_plural':'قراردادها','ordering':['-created_at']}),
        migrations.CreateModel(name='SubscriptionOperation', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),('operation_type', models.CharField(choices=[('create','ایجاد قرارداد'),('renew','تمدید'),('modify','ویرایش'),('payment','پرداخت'),('add_device','افزودن دستگاه'),('remove_device','حذف دستگاه'),('suspend','تعلیق'),('activate','فعال‌سازی'),('cancel','لغو')], max_length=30, verbose_name='نوع عملیات')),('performed_at', models.DateTimeField(auto_now_add=True, verbose_name='زمان عملیات')),('old_start_date', models.DateField(blank=True, null=True, verbose_name='شروع قبلی')),('new_start_date', models.DateField(blank=True, null=True, verbose_name='شروع جدید')),('old_end_date', models.DateField(blank=True, null=True, verbose_name='پایان قبلی')),('new_end_date', models.DateField(blank=True, null=True, verbose_name='پایان جدید')),('old_status', models.CharField(blank=True, max_length=20, verbose_name='وضعیت قبلی')),('new_status', models.CharField(blank=True, max_length=20, verbose_name='وضعیت جدید')),('notes', models.TextField(blank=True, verbose_name='یادداشت')),
            ('performed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='subscription_operations', to='accounts.user', verbose_name='انجام‌دهنده')),
            ('subscription', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='operations', to='organizations.subscription', verbose_name='قرارداد')),
        ], options={'verbose_name':'عملیات قرارداد','verbose_name_plural':'عملیات قرارداد','ordering':['-performed_at']}),
        migrations.CreateModel(name='SubscriptionOperationChange', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),('entity_type', models.CharField(max_length=50, verbose_name='نوع موجودیت')),('field_name', models.CharField(max_length=100, verbose_name='فیلد')),('old_value', models.TextField(blank=True, verbose_name='مقدار قبلی')),('new_value', models.TextField(blank=True, verbose_name='مقدار جدید')),
            ('operation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='changes', to='organizations.subscriptionoperation', verbose_name='عملیات')),
        ], options={'verbose_name':'تغییر عملیات','verbose_name_plural':'تغییرات عملیات','ordering':['id']}),
        migrations.CreateModel(name='SubscriptionDevice', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),('start_date', models.DateField(verbose_name='تاریخ شروع دستگاه')),('end_date', models.DateField(verbose_name='تاریخ پایان دستگاه')),('assigned_at', models.DateTimeField(auto_now_add=True, verbose_name='تاریخ اتصال')),('unassigned_at', models.DateTimeField(blank=True, null=True, verbose_name='تاریخ جدا شدن')),
            ('added_by_operation', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='added_devices', to='organizations.subscriptionoperation', verbose_name='عملیات افزودن')),
            ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='subscription_links', to='fleet.device', verbose_name='دستگاه')),
            ('removed_by_operation', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='removed_devices', to='organizations.subscriptionoperation', verbose_name='عملیات حذف')),
            ('subscription', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='subscription_devices', to='organizations.subscription', verbose_name='قرارداد')),
        ], options={'verbose_name':'دستگاه قرارداد','verbose_name_plural':'دستگاه‌های قرارداد','ordering':['-assigned_at']}),
        migrations.CreateModel(name='SubscriptionPayment', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),('amount', models.DecimalField(decimal_places=0, max_digits=15, verbose_name='مبلغ (ریال)')),('payment_date', models.DateField(verbose_name='تاریخ پرداخت')),('device_count', models.IntegerField(default=0, verbose_name='تعداد دستگاه این پرداخت')),('description', models.TextField(blank=True, verbose_name='توضیحات')),('created_at', models.DateTimeField(auto_now_add=True)),
            ('operation', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payments', to='organizations.subscriptionoperation', verbose_name='عملیات')),
            ('subscription', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payments', to='organizations.subscription', verbose_name='قرارداد')),
        ], options={'verbose_name':'پرداخت','verbose_name_plural':'پرداخت‌ها','ordering':['-payment_date']}),
    ]