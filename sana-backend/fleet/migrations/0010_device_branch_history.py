import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('fleet', '0009_device_replacement_returned_at'),
        ('organizations', '0003_contract_integrity_constraints'),
    ]

    operations = [
        migrations.CreateModel(
            name='DeviceBranchHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('started_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='شروع تخصیص شعبه')),
                ('ended_at', models.DateTimeField(blank=True, null=True, verbose_name='پایان تخصیص شعبه')),
                ('reason', models.CharField(blank=True, max_length=100, verbose_name='علت')),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='device_branch_history', to='organizations.branch', verbose_name='شعبه')),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='branch_history', to='fleet.device', verbose_name='دستگاه')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='device_branch_history', to='organizations.organization', verbose_name='سازمان مشتری')),
                ('subscription', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='device_branch_history', to='organizations.subscription', verbose_name='قرارداد')),
            ],
            options={
                'verbose_name': 'تاریخچه شعبه دستگاه',
                'verbose_name_plural': 'تاریخچه شعبه دستگاه‌ها',
                'ordering': ['-started_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='devicebranchhistory',
            constraint=models.UniqueConstraint(fields=('device',), condition=models.Q(ended_at__isnull=True), name='device_one_open_branch'),
        ),
        migrations.AddConstraint(
            model_name='devicebranchhistory',
            constraint=models.CheckConstraint(condition=models.Q(ended_at__isnull=True) | models.Q(ended_at__gte=models.F('started_at')), name='device_branch_valid_dates'),
        ),
        migrations.AddIndex(
            model_name='devicebranchhistory',
            index=models.Index(fields=['device', 'started_at'], name='dev_branch_hist_idx'),
        ),
    ]
