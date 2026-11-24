from django.db.models import F, OuterRef, Q, Subquery
from django.utils import timezone

from .models import DeviceCustomerAccessPeriod


def active_subscription_links(*, now=None):
    """Return each device's latest started assignment when its contract is valid."""
    from organizations.models import SubscriptionDevice

    now = now or timezone.now()
    today = timezone.localdate(now)
    latest_link_id = SubscriptionDevice.objects.filter(
        device_id=OuterRef('device_id'),
        assigned_at__lte=now,
    ).order_by('-assigned_at', '-id').values('pk')[:1]

    return SubscriptionDevice.objects.filter(
        pk=Subquery(latest_link_id),
        subscription__status='active',
        subscription__start_date__lte=today,
        subscription__end_date__gte=today,
        assigned_at__lte=now,
        unassigned_at__isnull=True,
        start_date__lte=today,
        end_date__gte=today,
    ).select_related('subscription')


def active_personal_contract_links(*, user_id, now=None):
    """Return the latest started assignment when it is valid for this user.

    A newer started assignment supersedes older rows even when its contract
    is suspended, expired, or belongs to another customer. Future assignments
    do not supersede the current assignment before assigned_at.
    """
    return active_subscription_links(now=now).filter(
        subscription__user_id=user_id,
        subscription__customer_type='personal',
    )


def active_customer_access_periods(*, organization_id=None, user_id=None, branch_id=None, now=None):
    """Return access periods backed by a currently valid contract-device assignment.

    A customer access row is not sufficient by itself: its contract must belong
    to the same customer, be active today, and still contain an active link to
    the same device. The access period itself must also be open and in range.
    """
    if bool(organization_id) == bool(user_id):
        return DeviceCustomerAccessPeriod.objects.none()

    now = now or timezone.now()
    today = timezone.localdate(now)

    # A device can have only one current customer/branch assignment.
    # If legacy data contains overlapping open periods, only the latest
    # started period may authorize access; an invalid newer period must not
    # reactivate an older customer's stale access row.
    latest_period_id = DeviceCustomerAccessPeriod.objects.filter(
        device_id=OuterRef('device_id'),
        started_at__lte=now,
    ).order_by('-started_at', '-id').values('pk')[:1]

    periods = DeviceCustomerAccessPeriod.objects.filter(
        pk=Subquery(latest_period_id),
        started_at__lte=now,
    ).filter(
        Q(ended_at__isnull=True) | Q(ended_at__gte=now),
        subscription__status='active',
        subscription__start_date__lte=today,
        subscription__end_date__gte=today,
        subscription__subscription_devices__device_id=F('device_id'),
        subscription__subscription_devices__assigned_at__lte=now,
        subscription__subscription_devices__unassigned_at__isnull=True,
        subscription__subscription_devices__start_date__lte=today,
        subscription__subscription_devices__end_date__gte=today,
    )

    if organization_id:
        periods = periods.filter(
            organization_id=organization_id,
            subscription__organization_id=organization_id,
            subscription__customer_type='organization',
        )
    else:
        periods = periods.filter(
            user_id=user_id,
            subscription__user_id=user_id,
            subscription__customer_type='personal',
        )

    if branch_id is not None:
        periods = periods.filter(branch_id=branch_id)

    if user_id:
        # A personal access period is valid only while its contract-device
        # link is the latest assignment that has actually started. A newer
        # invalid/ended assignment must not revive an older personal link.
        from organizations.models import SubscriptionDevice

        latest_link_id = SubscriptionDevice.objects.filter(
            device_id=OuterRef('device_id'),
            assigned_at__lte=now,
        ).order_by('-assigned_at', '-id').values('pk')[:1]
        periods = periods.filter(
            subscription__subscription_devices__pk=Subquery(latest_link_id)
        )

    return periods
