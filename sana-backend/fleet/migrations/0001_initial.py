# Generated manually to break the initial migration dependency cycle.
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(name='DeviceModel', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('manufacturer', models.CharField(max_length=100, verbose_name='سازنده')),
            ('name', models.CharField(max_length=100, verbose_name='نام مدل')),
            ('code', models.CharField(max_length=50, verbose_name='کد مدل')),
            ('protocol', models.CharField(max_length=50, verbose_name='پروتکل')),
            ('created_at', models.DateTimeField(auto_now_add=True)),
        ], options={'verbose_name':'مدل دستگاه','verbose_name_plural':'مدل‌های دستگاه','ordering':['manufacturer','name']}),
        migrations.CreateModel(name='VehicleType', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('name', models.CharField(max_length=100, verbose_name='نام نوع')),
            ('created_at', models.DateTimeField(auto_now_add=True)),
        ], options={'verbose_name':'نوع خودرو','verbose_name_plural':'انواع خودرو','ordering':['name']}),
        migrations.CreateModel(name='Vehicle', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('plate', models.CharField(max_length=20, verbose_name='پلاک')),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('vehicle_type', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='fleet.vehicletype', verbose_name='نوع خودرو')),
        ], options={'verbose_name':'خودرو','verbose_name_plural':'خودروها','ordering':['plate']}),
        migrations.CreateModel(name='Device', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('imei', models.CharField(max_length=20, unique=True, verbose_name='IMEI')),
            ('sim_number', models.CharField(blank=True, max_length=20, verbose_name='شماره SIM')),
            ('management_status', models.CharField(choices=[('warehouse','در انبار'),('sold','فروخته شده'),('installed','نصب شده'),('active','فعال'),('faulty','خراب'),('lost','گمشده'),('stolen','سرقت شده'),('disconnected','قطع سرویس')], default='warehouse', max_length=20, verbose_name='وضعیت مدیریتی')),
            ('installed_at', models.DateField(blank=True, null=True, verbose_name='تاریخ نصب')),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('device_model', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='devices', to='fleet.devicemodel', verbose_name='مدل دستگاه')),
            ('vehicle', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='devices', to='fleet.vehicle', verbose_name='خودرو')),
        ], options={'verbose_name':'دستگاه','verbose_name_plural':'دستگاه‌ها','ordering':['-created_at']}),
        migrations.CreateModel(name='Driver', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('first_name', models.CharField(max_length=100, verbose_name='نام')),
            ('last_name', models.CharField(max_length=100, verbose_name='نام خانوادگی')),
            ('national_id', models.CharField(blank=True, max_length=10, verbose_name='کد ملی')),
            ('mobile', models.CharField(max_length=15, verbose_name='موبایل')),
            ('personnel_code', models.CharField(blank=True, max_length=50, verbose_name='کد پرسنلی')),
            ('position', models.CharField(choices=[('driver','راننده'),('senior','راننده ارشد'),('supervisor','سرپرست رانندگان')], default='driver', max_length=20, verbose_name='سمت')),
            ('license_number', models.CharField(blank=True, max_length=50, verbose_name='شماره گواهینامه')),
            ('license_type', models.CharField(blank=True, max_length=50, verbose_name='نوع گواهینامه')),
            ('license_expiry', models.DateField(blank=True, null=True, verbose_name='تاریخ انقضا گواهینامه')),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
        ], options={'verbose_name':'راننده','verbose_name_plural':'رانندگان','ordering':['last_name','first_name']}),
    ]