from django.utils import timezone

from .models import DeviceLifecycleEvent


def record_device_lifecycle_event(
    *,
    device,
    event_type,
    performed_by=None,
    event_date=None,
    subscription=None,
    organization=None,
    user=None,
    vehicle=None,
    branch=None,
    reason='',
    description='',
    new_status=None,
):
    """ثبت رویداد و در صورت تعریف‌شدن، همگام‌سازی وضعیت فعلی دستگاه."""
    previous_status = device.management_status

    status_map = {
        'received': 'warehouse',
        'sold': 'sold',
        'assigned_to_contract': 'sold',
        'returned': 'warehouse',
        'sent_to_repair': 'faulty',
        'repaired': 'warehouse',
        'lost': 'lost',
        'stolen': 'stolen',
        'retired': 'retired',
        'disposed': 'disposed',
    }
    target_status = new_status if new_status is not None else status_map.get(event_type)

    if event_type in {'returned', 'repaired'}:
        device.organization = None
        device.owner_user = None
        device.branch = None
        device.vehicle = None

    if target_status and target_status != device.management_status:
        device.management_status = target_status
        device.save()
    elif event_type in {'returned', 'repaired'}:
        device.save()

    if organization is None:
        organization = device.organization
    if user is None:
        user = device.owner_user
    if vehicle is None:
        vehicle = device.vehicle
    if branch is None:
        branch = device.branch

    return DeviceLifecycleEvent.objects.create(
        device=device,
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
