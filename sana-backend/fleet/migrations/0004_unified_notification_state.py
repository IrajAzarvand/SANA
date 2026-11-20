# Unified notification identity and workflow fields on the existing alert-state table.
from django.db import migrations, models
import django.db.models.deletion


def populate_notification_keys(apps, schema_editor):
    State = apps.get_model('fleet', 'DeviceAlertState')
    for state in State.objects.all().iterator():
        state.event_key = f'gps:{state.device_id}:{state.traccar_event_id}'
        if state.status == 'new':
            state.status = 'unread'
        elif state.status == 'acknowledged':
            state.status = 'reviewed'
            state.read_at = state.acknowledged_at
            state.reviewed_at = state.acknowledged_at
        elif state.status == 'resolved':
            state.read_at = state.acknowledged_at or state.resolved_at
            state.reviewed_at = state.acknowledged_at
        state.notification_type = 'gps'
        state.save(update_fields=['event_key', 'status', 'read_at', 'reviewed_at', 'notification_type'])


class Migration(migrations.Migration):
    dependencies = [
        ('fleet', '0003_device_alert_state'),
        # Keep the fleet migration graph linear: this migration must follow
        # the parallel personal-alert-preference migration.
        ('fleet', '0004_personal_alert_preference'),
    ]

    operations = [
        migrations.AddField(
            model_name='devicealertstate',
            name='event_key',
            field=models.CharField(max_length=200, null=True, blank=True, verbose_name='شناسه یکتای اعلان'),
        ),
        migrations.AddField(
            model_name='devicealertstate',
            name='notification_type',
            field=models.CharField(default='gps', max_length=64, verbose_name='دسته اعلان'),
        ),
        migrations.AddField(
            model_name='devicealertstate',
            name='read_at',
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='devicealertstate',
            name='reviewed_at',
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.RunPython(populate_notification_keys, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='devicealertstate',
            name='event_key',
            field=models.CharField(max_length=200, verbose_name='شناسه یکتای اعلان'),
        ),
        migrations.AlterField(
            model_name='devicealertstate',
            name='device',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='alert_states',
                to='fleet.device',
                verbose_name='دستگاه',
            ),
        ),
        migrations.AlterField(
            model_name='devicealertstate',
            name='traccar_event_id',
            field=models.CharField(blank=True, default='', max_length=64, verbose_name='شناسه رویداد Traccar'),
        ),
        migrations.AlterField(
            model_name='devicealertstate',
            name='status',
            field=models.CharField(
                choices=[('unread', 'خوانده‌نشده'), ('read', 'خوانده‌شده'), ('reviewed', 'بررسی‌شده'), ('resolved', 'رفع‌شده')],
                default='unread',
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name='devicealertstate',
            constraint=models.UniqueConstraint(fields=('user', 'event_key'), name='fleet_alert_user_event_key_uniq'),
        ),
    ]
