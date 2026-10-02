# Generated manually for driver-to-vehicle assignment history.
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('fleet', '0002_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='DriverVehicleAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('started_at', models.DateTimeField(verbose_name='شروع تخصیص')),
                ('ended_at', models.DateTimeField(blank=True, null=True, verbose_name='پایان تخصیص')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('driver', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='vehicle_assignments', to='fleet.driver', verbose_name='راننده')),
                ('vehicle', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='driver_assignments', to='fleet.vehicle', verbose_name='خودرو')),
            ],
            options={
                'verbose_name': 'تخصیص راننده به خودرو',
                'verbose_name_plural': 'تخصیص‌های راننده به خودرو',
                'ordering': ['-started_at', '-id'],
                'indexes': [
                    models.Index(fields=['driver', 'started_at', 'ended_at'], name='fleet_drive_driver_i_7a0d2f_idx'),
                    models.Index(fields=['vehicle', 'started_at', 'ended_at'], name='fleet_drive_vehicle_i_4f7f7a_idx'),
                ],
            },
        ),
    ]
