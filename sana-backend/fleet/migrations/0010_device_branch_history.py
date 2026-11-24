import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


def backfill_branch_history(apps, schema_editor):
    Device = apps.get_model('fleet', 'Device')
    AccessPeriod = apps.get_model('fleet', 'DeviceCustomerAccessPeriod')
    SubscriptionDevice = apps.get_model('organizations', 'SubscriptionDevice')
    LifecycleEvent = apps.get_model('fleet', 'DeviceLifecycleEvent')
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
        closure_events = list(LifecycleEvent.objects.filter(
            device_id=device.pk,
            event_type__in=['sent_to_repair', 'lost', 'stolen', 'retired', 'disposed'],
        ).order_by('event_date', 'id'))
        event_index = 0
        group = []
        identity = None

        def flush_group(end_at=None, keep_open=False):
            nonlocal group, identity
            if not group:
                return
            first, last = group[0], group[-1]
            branch = first['period'].branch
            organization = first['period'].organization
            subscription = first['period'].subscription
            link = first['link']
            history_end = end_at if end_at is not None else last['ended_at']
            if link.unassigned_at is not None and (
                history_end is None or link.unassigned_at < history_end
            ):
                history_end = link.unassigned_at
            elif keep_open and link.unassigned_at is None:
                # A closed access period may only represent suspension/repair.
                # The branch assignment remains current while the contract link
                # itself remains assigned.
                history_end = None
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
                    ended_at=history_end,
                    reason='migration_backfill',
                )
            group, identity = [], None

        for period in periods:
            # These events end the physical branch assignment even if the
            # contract-device link remains open (repair, loss, theft, retirement).
            while (
                event_index < len(closure_events)
                and closure_events[event_index].event_date <= period.started_at
            ):
                flush_group(end_at=closure_events[event_index].event_date)
                event_index += 1

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
                # The next observed branch period is the best known boundary
                # for the previous branch assignment, including a transfer
                # performed during a suspension gap.
                flush_group(end_at=overlap_start)
                identity = key
            group.append({
                'period': period,
                'link': link,
                'started_at': overlap_start,
                'ended_at': overlap_end,
            })

        while event_index < len(closure_events):
            flush_group(end_at=closure_events[event_index].event_date)
            event_index += 1
        flush_group(keep_open=True)

        active_link = SubscriptionDevice.objects.filter(
            device_id=device.pk,
            unassigned_at__isnull=True,
        ).select_related('subscription').order_by('-assigned_at', '-id').first()
        if (
            active_link
            and active_link.subscription.customer_type == 'organization'
            and active_link.subscription.organization_id
            and device.branch_id
            and device.management_status in {'installed', 'active', 'disconnected'}
            and device.branch.organization_id == active_link.subscription.organization_id
        ):
            current_history = BranchHistory.objects.filter(
                device_id=device.pk,
                ended_at__isnull=True,
            ).first()
            if current_history and (
                current_history.subscription_id != active_link.subscription_id
                or current_history.branch_id != device.branch_id
                or current_history.organization_id != active_link.subscription.organization_id
            ):
                raise RuntimeError(
                    'Cannot safely backfill current branch history: the open history '
                    f'does not match the active contract/branch for device {device.pk}.'
                )
            if not current_history:
                latest_assignment_event = LifecycleEvent.objects.filter(
                    device_id=device.pk,
                    event_type__in=['assigned_to_contract', 'disposition', 'transferred'],
                    branch_id=device.branch_id,
                    event_date__gte=active_link.assigned_at,
                ).order_by('-event_date', '-id').first()
                branch_started_at = (
                    latest_assignment_event.event_date
                    if latest_assignment_event
                    else active_link.assigned_at
                )
                BranchHistory.objects.create(
                    device_id=device.pk,
                    organization_id=active_link.subscription.organization_id,
                    branch_id=device.branch_id,
                    subscription_id=active_link.subscription_id,
                    started_at=branch_started_at,
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
