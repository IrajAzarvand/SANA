from django.utils import timezone

from .models import DeviceLifecycleEvent


_EVENT_RELATION_UNSET = object()


def record_device_lifecycle_event(
    *,
    device,
    event_type,
    device_operation=None,
    performed_by=None,
    event_date=None,
    subscription=None,
    organization=_EVENT_RELATION_UNSET,
    user=_EVENT_RELATION_UNSET,
    vehicle=_EVENT_RELATION_UNSET,
    branch=_EVENT_RELATION_UNSET,
    reason='',
    description='',
    new_status=None,
):
    """ثبت رویداد و در صورت تعریف‌شدن، همگام‌سازی وضعیت فعلی دستگاه."""
    previous_status = device.management_status
    previous_organization = device.organization
    previous_user = device.owner_user
    previous_vehicle = device.vehicle
    previous_branch = device.branch

    status_map = {
        'received': 'warehouse',
        'assigned_to_contract': 'installed',
        'returned': 'warehouse',
        'sent_to_repair': 'in_repair',
        'repaired': 'ready',
        'lost': 'lost',
        'found': 'ready',
        'stolen': 'stolen',
        'retired': 'unusable',
        'disposed': 'disposed',
    }
    target_status = new_status if new_status is not None else status_map.get(event_type)

    if event_type == 'returned':
        # Returning hardware to the warehouse changes its physical location,
        # not its legal ownership. Ownership changes require an explicit transfer.
        device.branch = None
        device.vehicle = None

    if target_status and target_status != device.management_status:
        device.management_status = target_status
        device.save()
    elif event_type in {'returned', 'repaired'}:
        device.save()

    # Distinguish an omitted relation (inherit the previous value) from an
    # explicitly empty relation (for example, a personal customer has no org).
    if organization is _EVENT_RELATION_UNSET:
        organization = previous_organization
    if user is _EVENT_RELATION_UNSET:
        user = previous_user
    if vehicle is _EVENT_RELATION_UNSET:
        vehicle = previous_vehicle
    if branch is _EVENT_RELATION_UNSET:
        branch = previous_branch

    return DeviceLifecycleEvent.objects.create(
        device=device,
        device_operation=device_operation,
        event_type=event_type,
        event_date=event_date or timezone.now(),
        subscription=subscription,
        organization=organization,
        user=user,
        vehicle=vehicle,
        branch=branch,
        reason=reason,
        description=description,
        previous_status=previous_status,
        new_status=device.management_status,
        performed_by=performed_by,
    )
