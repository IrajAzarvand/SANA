import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


def backfill_branch_history(apps, schema_editor):
    Device = apps.get_model('fleet', 'Device')
    AccessPeriod = apps.get_model('fleet', 'DeviceCustomerAccessPeriod')
    SubscriptionDevice = apps.get_model('organizations', 'SubscriptionDevice')
    BranchHistory = apps.get_model('fleet', 'DeviceBranchHistory')

    for device in Device.objects.iterator():
        links_by_subscription = {}
        links = SubscriptionDevice.objects.filter(
            device_id=device.pk,
        ).select_related('subscription').order_by('assigned_at', 'id')
        for link in links:
            links_by_subscription.setdefault(link.subscription_id, []).append(link)

        periods = AccessPeriod.objects.filter(
            device_id=device.pk,
        ).select_related('branch', 'organization', 'subscription').order_by('started_at', 'id')
        group = []
        identity = None

        def flush_group():
            nonlocal group, identity
            if not group:
                return
            first, last = group[0], group[-1]
            branch = first['period'].branch
            organization = first['period'].organization
            subscription = first['period'].subscription
            if (
                branch
                and organization
                and branch.organization_id == organization.id
                and subscription
                and subscription.customer_type == 'organization'
                and subscription.organization_id == organization.id
            ):
                BranchHistory.objects.create(
                    device_id=device.pk,
                    organization_id=organization.id,
                    branch_id=branch.id,
                    subscription_id=subscription.id,
                    started_at=first['started_at'],
                    ended_at=last['ended_at'],
                    reason='migration_backfill',
                )
            group, identity = [], None

        for period in periods:
            if (
                not period.branch_id
                or not period.organization_id
                or not period.subscription_id
            ):
                flush_group()
                continue

            # A branch history segment belongs to a specific historical
            # contract-device link. Suspension may split access periods while
            # the link remains assigned, so those gaps are merged. Unassigning
            # and later reassigning the device creates a different link and
            # must produce a separate branch-history segment.
            candidates = []
            for link in links_by_subscription.get(period.subscription_id, []):
                overlap_start = max(period.started_at, link.assigned_at)
                possible_ends = [
                    value for value in (period.ended_at, link.unassigned_at)
                    if value is not None
                ]
                overlap_end = min(possible_ends) if possible_ends else None
                if overlap_end is not None and overlap_end <= overlap_start:
                    continue
                candidates.append((link, overlap_start, overlap_end))

            if len(candidates) > 1:
                raise RuntimeError(
                    'Cannot safely backfill branch history: overlapping contract-device '
                    f'links for device {device.pk}, subscription {period.subscription_id}.'
                )
            if not candidates:
                flush_group()
                continue

            link, overlap_start, overlap_end = candidates[0]
            key = (
                period.organization_id,
                period.branch_id,
                period.subscription_id,
                link.pk,
            )
            if identity != key:
                flush_group()
                identity = key
            group.append({
                'period': period,
                'started_at': overlap_start,
                'ended_at': overlap_end,
            })

        flush_group()

        if not BranchHistory.objects.filter(device_id=device.pk).exists():
            link = SubscriptionDevice.objects.filter(
                device_id=device.pk,
                unassigned_at__isnull=True,
            ).select_related('subscription').order_by('-assigned_at', '-id').first()
            if (
                link
                and link.subscription.customer_type == 'organization'
                and link.subscription.organization_id
                and device.branch_id
                and device.branch.organization_id == link.subscription.organization_id
            ):
                BranchHistory.objects.create(
                    device_id=device.pk,
                    organization_id=link.subscription.organization_id,
                    branch_id=device.branch_id,
                    subscription_id=link.subscription_id,
                    started_at=link.assigned_at,
                    reason='migration_active_link_backfill',
                )


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
        migrations.RunPython(backfill_branch_history, migrations.RunPython.noop),
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
