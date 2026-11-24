from django.db.models import F, Q
from django.utils import timezone

from .models import DeviceCustomerAccessPeriod


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

    periods = DeviceCustomerAccessPeriod.objects.filter(
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

    return periods
