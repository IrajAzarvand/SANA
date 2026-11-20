from django.utils import timezone
from django.utils.dateparse import parse_datetime
from datetime import datetime, timedelta, time as datetime_time
import math
from django.db import connection, transaction
from django.db.models import Exists, OuterRef, Prefetch, Q, Value
from django.db.models.functions import Concat, Lower
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle

from .models import VehicleType, Vehicle, DeviceModel, Device, Driver, DeviceLifecycleEvent, DeviceReplacementRelation, DeviceOperation, DeviceCustomerAccessPeriod, DeviceAlertState, PersonalAlertPreference, DriverVehicleAssignment
from .serializers import (
    VehicleTypeSerializer,
    VehicleSerializer,
    VehicleListSerializer,
    DeviceModelSerializer,
    DeviceSerializer,
    DeviceListSerializer,
    DriverSerializer,
    DeviceLifecycleEventSerializer,
    DeviceReplacementRelationSerializer,
    DeviceOperationSerializer,
    DriverVehicleAssignmentSerializer,
)
from organizations.models import SubscriptionDevice
from accounts.permissions import IsSiteAdmin, IsOrganizationMember
from .traccar_api import TraccarAPIError, traccar_current_positions, traccar_device_by_unique_id, traccar_device_positions, traccar_device_events, traccar_devices


def traccar_position_timestamp(position):
    """Return only Traccar's server-side receipt time.

    Device/fix timestamps are retained as raw diagnostics, but must never be
    used for freshness, ordering, or communication-state calculations.
    """
    return parse_datetime(str(position.get('serverTime') or ''))


def traccar_position_protocol(position):
    """Return the decoder protocol reported by Traccar for a position."""
    return str(position.get('protocol') or '').strip().lower()


def parse_report_history_cursor(raw_cursor_time, raw_cursor_id):
    """Parse a strict (fixTime, Traccar position ID) API pagination cursor."""
    if not raw_cursor_time:
        if raw_cursor_id not in (None, '', '0'):
            raise ValueError('cursor_id بدون cursor_time معتبر نیست.')
        return None, 0

    cursor_time = parse_datetime(raw_cursor_time)
    try:
        cursor_id = int(raw_cursor_id)
    except (TypeError, ValueError):
        raise ValueError('شناسه نشانگر صفحه‌بندی نامعتبر است.') from None

    if cursor_time is None or cursor_id <= 0:
        raise ValueError('نشانگر صفحه‌بندی نامعتبر است.')
    if timezone.is_naive(cursor_time):
        cursor_time = timezone.make_aware(cursor_time)
    return cursor_time, cursor_id


def normalize_traccar_history_positions(positions, range_start, range_end, cursor_time=None, cursor_id=0):
    """Validate, deduplicate and order Traccar history using serverTime only."""
    normalized = []
    seen_position_ids = set()

    for item in positions:
        try:
            point_id = int(item['id'])
            point_time = traccar_position_timestamp(item)
            latitude = float(item['latitude'])
            longitude = float(item['longitude'])
        except (KeyError, TypeError, ValueError, OverflowError):
            continue

        if point_time is None:
            continue
        if timezone.is_naive(point_time):
            point_time = timezone.make_aware(point_time)
        if point_time < range_start or point_time > range_end:
            continue
        if not math.isfinite(latitude) or not math.isfinite(longitude):
            continue
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            continue
        if point_id in seen_position_ids:
            continue
        seen_position_ids.add(point_id)

        if cursor_time is not None and (point_time, point_id) <= (cursor_time, cursor_id):
            continue
        normalized.append((point_time, point_id, item, latitude, longitude))

    normalized.sort(key=lambda row: (row[0], row[1]))
    return normalized


class VehicleTypeViewSet(viewsets.ModelViewSet):
    queryset = VehicleType.objects.all()
    serializer_class = VehicleTypeSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsSiteAdmin()]
        return super().get_permissions()

    def get_queryset(self):
        user = self.request.user
        if user.is_site_admin:
            return VehicleType.objects.all()
        if user.organization_id:
            return VehicleType.objects.filter(organization_id=user.organization_id)
        return VehicleType.objects.none()


class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.select_related('vehicle_type', 'organization', 'branch', 'owner_user').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['plate']
    ordering_fields = ['plate', 'created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return VehicleListSerializer
        return VehicleSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Vehicle.objects.select_related('vehicle_type', 'organization', 'branch', 'owner_user')

        if user.is_site_admin:
            pass
        elif user.is_main_user and user.organization:
            qs = qs.filter(organization=user.organization)
        elif user.is_branch_manager and user.branch:
            qs = qs.filter(branch=user.branch)
        elif user.is_personal_user:
            qs = qs.filter(owner_user=user)
        else:
            qs = qs.none()

        # فیلترها
        branch = self.request.query_params.get('branch')
        if branch:
            qs = qs.filter(branch_id=branch)

        organization = self.request.query_params.get('organization')
        if organization:
            qs = qs.filter(organization_id=organization)

        vehicle_type = self.request.query_params.get('vehicle_type')
        if vehicle_type:
            qs = qs.filter(vehicle_type_id=vehicle_type)

        return qs

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsSiteAdmin()]
        return super().get_permissions()


class DeviceModelViewSet(viewsets.ReadOnlyModelViewSet):
    """Legacy model metadata is readable, but model CRUD is no longer part of device registration."""
    queryset = DeviceModel.objects.filter(is_verified=True)
    serializer_class = DeviceModelSerializer
    pagination_class = None
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['manufacturer', 'name', 'code', 'protocol']
    ordering_fields = ['manufacturer', 'name', 'created_at']


class DeviceViewSet(viewsets.ModelViewSet):
    queryset = Device.objects.select_related('device_model', 'organization', 'branch', 'vehicle', 'owner_user').all()
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'device_list'
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['imei', 'sim_number', 'device_model__manufacturer', 'device_model__name']
    ordering_fields = ['created_at', 'imei']

    def get_serializer_class(self):
        if self.action == 'list':
            return DeviceListSerializer
        return DeviceSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Device.objects.select_related(
            'device_model', 'organization', 'branch', 'vehicle', 'owner_user',
            'current_holder_organization', 'current_holder_user',
        )

        # The list serializer needs a compact, preloaded snapshot of the
        # subscription and replacement history. Keep these prefetches off
        # detail/actions so unrelated endpoints do not pay for list-only data.
        if self.action == 'list':
            replacement_operation_types = (
                'return_for_repair',
                'temporary_replacement',
                'permanent_replacement',
            )
            qs = qs.prefetch_related(
                Prefetch(
                    'replacement_relations_as_source',
                    queryset=DeviceReplacementRelation.objects.select_related(
                        'replacement_device'
                    ).order_by('-replacement_date', '-id'),
                    to_attr='_replacement_relations_as_source',
                ),
                Prefetch(
                    'replacement_relations_as_replacement',
                    queryset=DeviceReplacementRelation.objects.select_related(
                        'source_device'
                    ).order_by('-replacement_date', '-id'),
                    to_attr='_replacement_relations_as_replacement',
                ),
                Prefetch(
                    'subscription_links',
                    queryset=SubscriptionDevice.objects.select_related(
                        'subscription'
                    ).order_by('-assigned_at', '-id'),
                    to_attr='_prefetched_subscription_links',
                ),
                Prefetch(
                    'operations',
                    queryset=DeviceOperation.objects.filter(
                        replacement_device__isnull=False,
                        subscription__isnull=False,
                        operation_type__in=replacement_operation_types,
                    ).select_related('subscription').order_by('-performed_at', '-id'),
                    to_attr='_prefetched_replacement_source_operations',
                ),
                Prefetch(
                    'replacement_operations',
                    queryset=DeviceOperation.objects.filter(
                        subscription__isnull=False,
                        operation_type__in=replacement_operation_types,
                    ).select_related('subscription').order_by('-performed_at', '-id'),
                    to_attr='_prefetched_replacement_target_operations',
                ),
            )

        if user.is_site_admin:
            pass
        elif user.is_main_user and user.organization:
            now = timezone.now()
            qs = qs.filter(
                customer_access_periods__organization=user.organization,
                customer_access_periods__started_at__lte=now,
                customer_access_periods__ended_at__isnull=True,
            ).distinct()
        elif user.is_branch_manager and user.branch:
            now = timezone.now()
            qs = qs.filter(
                customer_access_periods__organization=user.organization,
                customer_access_periods__branch=user.branch,
                customer_access_periods__started_at__lte=now,
                customer_access_periods__ended_at__isnull=True,
            ).distinct()
        elif user.is_personal_user:
            now = timezone.now()
            today = timezone.localdate()
            active_access = DeviceCustomerAccessPeriod.objects.filter(
                device=OuterRef('pk'),
                user=user,
                started_at__lte=now,
            ).filter(
                Q(ended_at__isnull=True) | Q(ended_at__gte=now)
            )
            active_contract_link = SubscriptionDevice.objects.filter(
                device=OuterRef('pk'),
                subscription__user=user,
                subscription__status='active',
                subscription__start_date__lte=today,
                subscription__end_date__gte=today,
                unassigned_at__isnull=True,
                start_date__lte=today,
                end_date__gte=today,
            )
            qs = qs.filter(
                Q(Exists(active_access)) | Q(Exists(active_contract_link))
            )
        else:
            qs = qs.none()

        # ─── فیلترها ───

        # فیلتر شعبه
        branch = self.request.query_params.get('branch')
        if branch:
            qs = qs.filter(branch_id=branch)

        # فیلتر سازمان
        organization = self.request.query_params.get('organization')
        if organization:
            qs = qs.filter(organization_id=organization)

        # فیلتر وضعیت مدیریتی
        status = self.request.query_params.get('management_status')
        if status:
            qs = qs.filter(management_status=status)

        # فیلتر «فقط انبار» — دستگاه‌هایی که هیچ اتصال فعالی به قرارداد ندارن
        in_warehouse = self.request.query_params.get('in_warehouse')
        if in_warehouse == 'true':
            active_links = SubscriptionDevice.objects.filter(
                device=OuterRef('pk'),
                unassigned_at__isnull=True,
            )
            qs = qs.annotate(
                has_active_link=Exists(active_links)
            ).filter(
                management_status='warehouse',
                has_active_link=False,
            )

            
        # فیلتر «فقط فعال» — دستگاه‌هایی که یه اتصال فعال به قرارداد دارن
        active = self.request.query_params.get('active')
        if active == 'true':
            today = timezone.now().date()
            qs = qs.filter(
                subscription_links__unassigned_at__isnull=True,
                subscription_links__start_date__lte=today,
                subscription_links__end_date__gte=today,
                subscription_links__subscription__status='active',
            ).distinct()

        return qs

    @staticmethod
    def _sync_models_from_traccar(devices, traccar_by_imei):
        """Persist only exact, verified model matches explicitly reported by Traccar.

        Traccar's device name is user-defined and is deliberately not treated as
        hardware metadata. If model is absent or cannot be matched confidently,
        the existing SANA model is left untouched.
        """
        reported_by_device = {}
        reported_models = set()
        for device in devices:
            traccar_device = traccar_by_imei.get(str(device.imei).strip())
            if not traccar_device:
                continue
            reported_model = " ".join(
                str(traccar_device.get('model') or '').split()
            ).lower()
            if reported_model:
                reported_by_device[device.pk] = (device, reported_model)
                reported_models.add(reported_model)

        # Avoid loading the entire verified catalog (currently thousands of
        # rows) on every six-second device-list poll. Ask the database only
        # for exact full-label or model-name candidates actually reported by
        # the Traccar devices in this page.
        if not reported_models:
            return

        catalog = list(
            DeviceModel.objects.filter(is_verified=True)
            .annotate(
                normalized_full_label=Lower(
                    Concat('manufacturer', Value(' '), 'name')
                ),
                normalized_name=Lower('name'),
            )
            .filter(
                Q(normalized_full_label__in=reported_models)
                | Q(normalized_name__in=reported_models)
            )
            .only('id', 'manufacturer', 'name')
        )
        full_labels = {}
        models_by_name = {}
        for model in catalog:
            full_label = " ".join(
                f"{model.manufacturer} {model.name}".split()
            ).lower()
            full_labels.setdefault(full_label, model)
            name_key = " ".join(model.name.split()).lower()
            models_by_name.setdefault(name_key, []).append(model)

        for device, reported_model in reported_by_device.values():
            # Full manufacturer + model is unambiguous. A model-only match is
            # accepted only when that model name belongs to exactly one brand.
            matched_model = full_labels.get(reported_model)
            if matched_model is None:
                candidates = models_by_name.get(reported_model, [])
                if len(candidates) == 1:
                    matched_model = candidates[0]
            if matched_model and device.device_model_id != matched_model.id:
                device.device_model = matched_model
                device.save(update_fields=['device_model', 'updated_at'])

    def list(self, request, *args, **kwargs):
        """List authorized SANA devices and use Traccar for last-seen timestamps."""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        devices = list(page if page is not None else queryset)

        # Traccar is the source of GPS receipt timestamps; SANA only adds this
        # transient serializer attribute and does not persist a duplicate timestamp.
        for device in devices:
            device.last_data_received_at = None
            device.traccar_protocol = None

        traccar_by_imei = {}
        try:
            traccar_by_imei = {
                str(item.get('uniqueId') or '').strip(): item
                for item in traccar_devices()
                if str(item.get('uniqueId') or '').strip()
            }
        except TraccarAPIError:
            # Keep the device list available during a temporary Traccar outage.
            pass

        # Keep Traccar's explicit model value as transient list metadata.
        # It is not persisted: the verified SANA catalog remains the source
        # of normalized manufacturer/model records.
        for device in devices:
            traccar_device = traccar_by_imei.get(str(device.imei).strip())
            device.traccar_model = " ".join(
                str((traccar_device or {}).get('model') or '').split()
            ) or None

        # Only explicit Traccar model metadata can update the SANA catalog link.
        # User-defined Traccar device names are not considered model evidence.
        self._sync_models_from_traccar(devices, traccar_by_imei)

        # /positions supplies serverTime: when Traccar received the position.
        # GPS-originated fixTime/deviceTime are deliberately not used for this field.
        received_at_by_traccar_id = {}
        protocol_by_traccar_id = {}
        if traccar_by_imei:
            try:
                for position in traccar_current_positions():
                    try:
                        traccar_id = int(position.get('deviceId'))
                    except (TypeError, ValueError):
                        continue

                    # Position.protocol is Traccar's actual decoder protocol.
                    # Read it independently from serverTime: a valid protocol
                    # remains useful even if a position has no receipt timestamp.
                    protocol = traccar_position_protocol(position)
                    if protocol:
                        protocol_by_traccar_id[traccar_id] = protocol

                    received_at = parse_datetime(str(position.get('serverTime') or ''))
                    if received_at is not None:
                        received_at_by_traccar_id[traccar_id] = received_at
            except TraccarAPIError:
                # Without /positions, neither live protocol nor receipt time is available.
                pass

        for device in devices:
            traccar_device = traccar_by_imei.get(str(device.imei).strip())
            traccar_id = traccar_device.get('id') if traccar_device else None
            received_at = None
            if traccar_id is not None:
                try:
                    received_at = received_at_by_traccar_id.get(int(traccar_id))
                except (TypeError, ValueError):
                    pass
            # No fallback to /devices.lastUpdate: serverTime is the
            # authoritative receipt timestamp and may legitimately be absent.
            device.last_data_received_at = received_at
            if traccar_id is not None:
                try:
                    device.traccar_protocol = protocol_by_traccar_id.get(int(traccar_id))
                except (TypeError, ValueError):
                    device.traccar_protocol = None

        serializer = self.get_serializer(devices, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


    @action(detail=False, methods=['get', 'put'], url_path='alert-preferences', throttle_classes=[ScopedRateThrottle], throttle_scope='personal_alert_preferences')
    def alert_preferences(self, request):
        """Read or update the signed-in personal user's Traccar alert filters."""
        if not request.user.is_personal_user:
            return Response({'detail': 'این تنظیمات فقط برای مشتری شخصی فعال است.'}, status=403)

        if request.method == 'GET':
            preference = PersonalAlertPreference.objects.filter(user=request.user).first()
            disabled = preference.disabled_event_types if preference else []
            return Response({'disabled_event_types': disabled})

        disabled = request.data.get('disabled_event_types', [])
        if (
            not isinstance(disabled, list)
            or any(not isinstance(item, str) for item in disabled)
            or len(disabled) > 100
        ):
            return Response({'detail': 'فهرست انواع هشدار نامعتبر است.'}, status=400)

        allowed_types = set(["commandResult","deviceOnline","deviceUnknown","deviceOffline","deviceInactive","queuedCommandSent","deviceMoving","deviceStopped","deviceOverspeed","overspeed","deviceFuelDrop","deviceFuelIncrease","geofenceEnter","geofenceExit","geofenceCrossed","proximityEnter","proximityExit","unaccompaniedMotion","alarm","ignitionOn","ignitionOff","maintenance","driverChanged","media"])
        if any(item not in allowed_types for item in disabled):
            return Response({'detail': 'یکی از انواع هشدار انتخاب‌شده معتبر نیست.'}, status=400)

        preference, _created = PersonalAlertPreference.objects.update_or_create(
            user=request.user,
            defaults={'disabled_event_types': sorted(set(disabled))},
        )
        return Response({'disabled_event_types': preference.disabled_event_types})

    @action(detail=False, methods=['get', 'post'], url_path='alerts', throttle_classes=[ScopedRateThrottle], throttle_scope='personal_alerts')
    def alerts(self, request):
        """Read authorized Traccar events and persist only per-user workflow state."""
        if not (
            request.user.is_personal_user
            or request.user.is_site_admin
            or request.user.is_main_user
            or request.user.is_branch_manager
        ):
            return Response({'detail': 'اجازه مشاهده هشدارها را ندارید.'}, status=403)

        if request.method == 'POST':
            if request.data.get('mark_all') is True:
                visible_device_ids = self.get_queryset().values_list('pk', flat=True)
                updated = DeviceAlertState.objects.filter(
                    user=request.user,
                    device_id__in=visible_device_ids,
                    status='new',
                ).update(status='acknowledged', acknowledged_at=timezone.now())
                return Response({'updated': updated})

            raw_device_id = request.data.get('device_id')
            event_id = str(request.data.get('event_id') or '').strip()
            requested_status = str(request.data.get('status') or '').strip()
            if requested_status not in {'acknowledged', 'resolved'} or not event_id:
                return Response({'detail': 'شناسه رویداد و وضعیت معتبر الزامی است.'}, status=400)
            try:
                device_id = int(raw_device_id)
            except (TypeError, ValueError):
                return Response({'detail': 'شناسه دستگاه نامعتبر است.'}, status=400)

            device = self.get_queryset().filter(pk=device_id).first()
            if device is None:
                return Response({'detail': 'دستگاه یافت نشد یا مجوز مشاهده آن را ندارید.'}, status=404)
            state = DeviceAlertState.objects.filter(
                user=request.user, device=device, traccar_event_id=event_id
            ).first()
            if state is None:
                return Response({'detail': 'رویداد موردنظر یافت نشد.'}, status=404)
            state.status = requested_status
            if requested_status == 'acknowledged':
                state.acknowledged_at = timezone.now()
            else:
                state.resolved_at = timezone.now()
            state.save(update_fields=['status', 'acknowledged_at', 'resolved_at'])
            return Response({
                'device_id': device.pk,
                'event_id': state.traccar_event_id,
                'status': state.status,
                'acknowledged_at': state.acknowledged_at,
                'resolved_at': state.resolved_at,
            })

        now = timezone.now()
        default_start = now - timedelta(days=30)
        raw_start = parse_datetime(request.query_params.get('from', '')) if request.query_params.get('from') else default_start
        raw_end = parse_datetime(request.query_params.get('to', '')) if request.query_params.get('to') else now
        if raw_start is None or raw_end is None:
            return Response({'detail': 'بازه زمانی هشدارها نامعتبر است.'}, status=400)
        if timezone.is_naive(raw_start):
            raw_start = timezone.make_aware(raw_start)
        if timezone.is_naive(raw_end):
            raw_end = timezone.make_aware(raw_end)
        if raw_start > raw_end or raw_end > now + timedelta(minutes=1):
            return Response({'detail': 'بازه زمانی انتخاب‌شده معتبر نیست.'}, status=400)
        if raw_end - raw_start > timedelta(days=90):
            return Response({'detail': 'بازه زمانی هشدارها نمی‌تواند بیشتر از ۹۰ روز باشد.'}, status=400)

        devices = list(self.get_queryset().select_related('vehicle'))
        if not devices:
            return Response({'results': [], 'counts': {'all': 0, 'new': 0, 'acknowledged': 0, 'resolved': 0}})

        contract_by_device = {}
        access_by_device = {}
        if request.user.is_personal_user:
            today = timezone.localdate()
            links = SubscriptionDevice.objects.filter(
                device__in=devices,
                unassigned_at__isnull=True,
                subscription__user=request.user,
                subscription__status='active',
                start_date__lte=today,
                end_date__gte=today,
                subscription__start_date__lte=today,
                subscription__end_date__gte=today,
            ).select_related('subscription')
            contract_by_device = {link.device_id: link for link in links}
        elif not request.user.is_site_admin:
            access_periods = DeviceCustomerAccessPeriod.objects.filter(
                device__in=devices,
                started_at__lte=now,
                ended_at__isnull=True,
            )
            if request.user.is_main_user:
                access_periods = access_periods.filter(organization=request.user.organization)
            elif request.user.is_branch_manager:
                access_periods = access_periods.filter(
                    organization=request.user.branch.organization,
                    branch=request.user.branch,
                )
            access_by_device = {period.device_id: period for period in access_periods}

        if request.user.is_personal_user:
            preference = PersonalAlertPreference.objects.filter(user=request.user).only('disabled_event_types').first()
            disabled_event_types = set(preference.disabled_event_types or []) if preference else set()
        else:
            disabled_event_types = set()

        results = []
        try:
            for device in devices:
                if request.user.is_personal_user:
                    link = contract_by_device.get(device.pk)
                    if link is None:
                        continue
                    contract_start = timezone.make_aware(datetime.combine(
                        max(link.start_date, link.subscription.start_date), datetime_time.min
                    ))
                    contract_end = timezone.make_aware(datetime.combine(
                        min(link.end_date, link.subscription.end_date), datetime_time.max
                    ))
                elif request.user.is_site_admin:
                    contract_start = raw_start
                    contract_end = raw_end
                else:
                    access_period = access_by_device.get(device.pk)
                    if access_period is None:
                        continue
                    contract_start = access_period.started_at
                    contract_end = access_period.ended_at or now
                event_start = max(raw_start, contract_start)
                event_end = min(raw_end, contract_end, now)
                if event_start > event_end:
                    continue

                traccar_device = traccar_device_by_unique_id(device.imei)
                if not traccar_device or traccar_device.get('id') is None:
                    continue
                events = traccar_device_events(
                    int(traccar_device['id']),
                    event_start.isoformat().replace('+00:00', 'Z'),
                    event_end.isoformat().replace('+00:00', 'Z'),
                )
                for event in sorted(events, key=lambda item: str(item.get('eventTime') or '')):
                    event_id = str(event.get('id') or '').strip()
                    event_type = str(event.get('type') or '').strip()
                    event_time = parse_datetime(str(event.get('eventTime') or ''))
                    if not event_id or not event_type or event_time is None:
                        continue
                    if timezone.is_naive(event_time):
                        event_time = timezone.make_aware(event_time)

                    state, _created = DeviceAlertState.objects.update_or_create(
                        user=request.user,
                        device=device,
                        traccar_event_id=event_id,
                        defaults={'event_type': event_type, 'event_time': event_time},
                    )
                    if event_type == 'deviceOnline':
                        DeviceAlertState.objects.filter(
                            user=request.user,
                            device=device,
                            event_type='deviceOffline',
                            event_time__lt=event_time,
                        ).exclude(status='resolved').update(
                            status='resolved', resolved_at=event_time
                        )
                        for previous_alert in results:
                            if (
                                previous_alert['device_id'] == device.pk
                                and previous_alert['type'] == 'deviceOffline'
                                and previous_alert['event_time'] < event_time
                            ):
                                previous_alert['status'] = 'resolved'
                                previous_alert['resolved_at'] = event_time

                    if event_type in disabled_event_types:
                        continue

                    results.append({
                        'id': state.traccar_event_id,
                        'device_id': device.pk,
                        'device_imei': device.imei,
                        'vehicle_plate': device.vehicle.plate if device.vehicle_id else None,
                        'type': state.event_type,
                        'event_time': state.event_time,
                        'status': state.status,
                        'acknowledged_at': state.acknowledged_at,
                        'resolved_at': state.resolved_at,
                        'attributes': event.get('attributes') if isinstance(event.get('attributes'), dict) else {},
                    })
        except TraccarAPIError:
            return Response({'detail': 'دریافت رویدادها از Traccar در حال حاضر ممکن نیست.'}, status=503)

        results.sort(key=lambda item: (item['event_time'], item['id']), reverse=True)
        counts = {
            'all': len(results),
            'new': sum(item['status'] == 'new' for item in results),
            'acknowledged': sum(item['status'] == 'acknowledged' for item in results),
            'resolved': sum(item['status'] == 'resolved' for item in results),
        }
        return Response({'results': results, 'counts': counts})

    @action(detail=False, methods=['get'], url_path='report-history', throttle_classes=[ScopedRateThrottle], throttle_scope='personal_report_history')
    def report_history(self, request):
        """Return authorized device history for map playback; customer dates are contract-bounded."""
        raw_device_id = request.query_params.get('device_id')
        if not raw_device_id:
            return Response({'detail': 'انتخاب دستگاه الزامی است.'}, status=400)
        try:
            device_id = int(raw_device_id)
            if device_id <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return Response({'detail': 'شناسه دستگاه نامعتبر است.'}, status=400)

        device = self.get_queryset().filter(pk=device_id).select_related('vehicle').first()
        if device is None:
            return Response({'detail': 'دستگاه یافت نشد یا مجوز مشاهده آن را ندارید.'}, status=404)

        range_start = range_end = None
        if not request.user.is_site_admin:
            now = timezone.now()
            today = timezone.localdate()
            links = list(
                SubscriptionDevice.objects.filter(
                    device=device,
                    unassigned_at__isnull=True,
                    subscription__status__in=['active', 'expired'],
                ).select_related('subscription').order_by('-start_date', '-id')
            )
            access_query = DeviceCustomerAccessPeriod.objects.filter(
                device=device,
                started_at__lte=now,
            ).filter(
                Q(ended_at__isnull=True) | Q(ended_at__gte=now)
            )

            if request.user.is_personal_user:
                # Personal device visibility is granted by either a current
                # customer-access period or a current active contract link.
                # Report authorization must follow the same rule as get_queryset().
                personal_links = [
                    link for link in links
                    if link.subscription.user_id == request.user.pk
                    and link.subscription.status == 'active'
                    and link.start_date <= today <= link.end_date
                    and link.subscription.start_date <= today <= link.subscription.end_date
                ]
                link = personal_links[0] if personal_links else None

                if link is None:
                    return Response({'detail': 'گزارش این دستگاه فقط در بازه قرارداد فعال قابل مشاهده است.'}, status=403)

                # Contract dates are the sole reporting boundary for personal
                # users. Operational access periods do not extend or narrow it.
                range_start = timezone.make_aware(datetime.combine(
                    max(link.start_date, link.subscription.start_date),
                    datetime_time.min,
                ))
                range_end = timezone.make_aware(datetime.combine(
                    min(link.end_date, link.subscription.end_date),
                    datetime_time.max,
                ))
            else:
                if request.user.is_branch_manager:
                    access_query = access_query.filter(
                        organization_id=request.user.organization_id,
                        branch_id=request.user.branch_id,
                    )
                    links = [
                        link for link in links
                        if link.subscription.organization_id == request.user.organization_id
                    ]
                elif request.user.is_main_user:
                    access_query = access_query.filter(organization_id=request.user.organization_id)
                    links = [
                        link for link in links
                        if link.subscription.organization_id == request.user.organization_id
                    ]
                else:
                    links = []

                access = access_query.order_by('-started_at').first()
                if not links or access is None:
                    return Response({'detail': 'برای این دستگاه قرارداد و دسترسی فعال پیدا نشد.'}, status=403)

                link = links[0]
                start_date = max(link.start_date, link.subscription.start_date, timezone.localdate(access.started_at))
                end_date = min(link.end_date, link.subscription.end_date)
                if access.ended_at:
                    end_date = min(end_date, timezone.localdate(access.ended_at))
                contract_start = timezone.make_aware(datetime.combine(start_date, datetime_time.min))
                contract_end = timezone.make_aware(datetime.combine(end_date, datetime_time.max))
                range_start = max(contract_start, access.started_at)
                range_end = min(contract_end, access.ended_at) if access.ended_at else contract_end

        if request.query_params.get('metadata') == 'true':
            return Response({
                'device': {
                    'id': device.pk,
                    'imei': device.imei,
                    'sim_number': device.sim_number,
                    'vehicle_plate': device.vehicle.plate if device.vehicle_id else None,
                },
                'range_start': range_start.isoformat() if range_start else None,
                'range_end': range_end.isoformat() if range_end else None,
                'unrestricted': bool(request.user.is_site_admin),
            })

        raw_start = parse_datetime(request.query_params.get('from', ''))
        raw_end = parse_datetime(request.query_params.get('to', ''))
        if raw_start is None or raw_end is None:
            return Response({'detail': 'تاریخ و ساعت شروع و پایان الزامی است.'}, status=400)
        if timezone.is_naive(raw_start):
            raw_start = timezone.make_aware(raw_start)
        if timezone.is_naive(raw_end):
            raw_end = timezone.make_aware(raw_end)
        if raw_start > raw_end:
            return Response({'detail': 'زمان شروع باید قبل از زمان پایان باشد.'}, status=400)
        if range_start and (raw_start < range_start or raw_end > range_end):
            return Response({
                'detail': 'بازه انتخابی خارج از محدوده مجاز قرارداد یا دسترسی دستگاه است.',
                'range_start': range_start.isoformat(),
                'range_end': range_end.isoformat(),
            }, status=403)

        try:
            cursor_fix_time, cursor_id = parse_report_history_cursor(
                request.query_params.get('cursor_fix_time'),
                request.query_params.get('cursor_id'),
            )
        except ValueError:
            return Response({'detail': 'نشانگر صفحه‌بندی نامعتبر است.'}, status=400)

        # Traccar filters historical positions by fixTime and returns them
        # oldest-first. Continue from the last fixTime of the previous page;
        # do not refetch the complete selected period on every page.
        limit = 5000
        query_start = cursor_fix_time or raw_start
        try:
            traccar_device = traccar_device_by_unique_id(device.imei)
            if traccar_device is None or traccar_device.get('id') is None:
                return Response({'detail': 'دستگاه در Traccar ثبت نشده است.'}, status=404)
            positions = traccar_device_positions(
                int(traccar_device['id']),
                query_start.isoformat().replace('+00:00', 'Z'),
                raw_end.isoformat().replace('+00:00', 'Z'),
                limit=limit + 1,
            )
        except TraccarAPIError:
            return Response({'detail': 'دریافت تاریخچه از Traccar موقتاً ممکن نیست.'}, status=503)

        def fix_time_key(item):
            value = parse_datetime(str(item.get('fixTime') or ''))
            if value is None:
                return None
            if timezone.is_naive(value):
                value = timezone.make_aware(value)
            try:
                position_id = int(item.get('id') or 0)
            except (TypeError, ValueError):
                position_id = 0
            return value, position_id

        positions = [
            item for item in positions
            if fix_time_key(item) is not None
            and (
                cursor_fix_time is None
                or fix_time_key(item) > (cursor_fix_time, cursor_id)
            )
        ]
        positions.sort(key=fix_time_key)
        has_more = len(positions) > limit
        page_positions = positions[:limit]
        next_cursor = None
        if has_more and page_positions:
            latest_key = fix_time_key(page_positions[-1])
            next_cursor = {
                'cursor_fix_time': latest_key[0].isoformat(),
                'cursor_id': latest_key[1],
            }

        normalized = normalize_traccar_history_positions(
            page_positions, raw_start, raw_end,
        )
        point_ids = [row[1] for row in normalized]
        matches = {}
        if point_ids:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT traccar_position_id, matched_latitude, matched_longitude,
                           match_provider, matched_at
                    FROM gps.map_matched_position
                    WHERE traccar_position_id = ANY(%s)
                    """,
                    [point_ids],
                )
                matches = {
                    int(row[0]): {
                        'matched_latitude': float(row[1]),
                        'matched_longitude': float(row[2]),
                        'match_provider': row[3],
                        'matched_at': row[4].isoformat() if row[4] else None,
                    }
                    for row in cursor.fetchall()
                }

        points = []
        for point_time, point_id, item, latitude, longitude in normalized:
            attributes = item.get('attributes') if isinstance(item.get('attributes'), dict) else {}
            match = matches.get(point_id, {})
            points.append({
                'id': point_id,
                'traccar_position_id': point_id,
                'device_time': point_time.isoformat(),
                'server_received_at': item.get('serverTime'),
                'latitude': latitude,
                'longitude': longitude,
                'matched_latitude': match.get('matched_latitude'),
                'matched_longitude': match.get('matched_longitude'),
                'match_provider': match.get('match_provider'),
                'matched_at': match.get('matched_at'),
                'gps_valid': bool(item.get('valid', True)),
                'accuracy': item.get('accuracy'),
                'speed': float(item.get('speed') or 0) * 1.852,
                'heading': item.get('course'),
                'altitude': item.get('altitude'),
                'motion': attributes.get('motion'),
                'ignition': attributes.get('ignition'),
                'satellites': attributes.get('sat'),
                'battery_voltage': attributes.get('battery'),
                'external_voltage': attributes.get('power'),
                'gsm_signal': attributes.get('rssi'),
                'odometer': attributes.get('odometer'),
                'engine_hours': attributes.get('hours'),
                'fuel_level': attributes.get('fuel'),
                'attributes': attributes,
            })

        return Response({
            'device': {
                'id': device.pk,
                'imei': device.imei,
                'sim_number': device.sim_number,
                'vehicle_plate': device.vehicle.plate if device.vehicle_id else None,
            },
            'points': points,
            'next_cursor': next_cursor,
            'range_start': range_start.isoformat() if range_start else None,
            'range_end': range_end.isoformat() if range_end else None,
            'unrestricted': bool(request.user.is_site_admin),
        })

    @action(detail=False, methods=['post'], url_path='map-matching-activity', throttle_classes=[ScopedRateThrottle], throttle_scope='personal_map_activity')
    def map_matching_activity(self, request):
        """Heartbeat for a visible map; the GPS worker expires abandoned sessions."""
        session_id = request.data.get('session_id')
        active = request.data.get('active', True)
        if not isinstance(session_id, str) or not session_id or len(session_id) > 100:
            return Response({'detail': 'شناسه نشست نقشه نامعتبر است.'}, status=400)
        if not isinstance(active, bool):
            return Response({'detail': 'مقدار active باید بولی باشد.'}, status=400)

        with connection.cursor() as cursor:
            if active:
                cursor.execute(
                    """
                    INSERT INTO gps.map_matching_watchers AS watcher
                        (session_id, user_id, expires_at, updated_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP + INTERVAL '45 seconds', CURRENT_TIMESTAMP)
                    ON CONFLICT (session_id) DO UPDATE
                    SET expires_at = EXCLUDED.expires_at,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE watcher.user_id = EXCLUDED.user_id
                    """,
                    [session_id, request.user.pk],
                )
            else:
                cursor.execute(
                    "DELETE FROM gps.map_matching_watchers WHERE session_id = %s AND user_id = %s",
                    [session_id, request.user.pk],
                )
        return Response({'active': active})

    @action(detail=False, methods=['get'], url_path='map-positions', throttle_classes=[ScopedRateThrottle], throttle_scope='personal_map_positions')
    def map_positions(self, request):
        """Return one live-map record for every device the current user may access."""
        devices = list(self.filter_queryset(self.get_queryset()).select_related('vehicle'))
        if not devices:
            return Response([])

        sana_by_imei = {str(device.imei).strip(): device for device in devices}
        try:
            traccar_devices_list = traccar_devices()
            traccar_positions = traccar_current_positions()
        except TraccarAPIError:
            return Response(
                {'detail': 'دریافت موقعیت زنده از Traccar موقتاً ممکن نیست.'},
                status=503,
            )

        traccar_by_imei = {}
        for item in traccar_devices_list:
            try:
                traccar_id = int(item.get('id'))
            except (TypeError, ValueError):
                continue
            unique_id = str(item.get('uniqueId') or '').strip()
            if unique_id:
                traccar_by_imei[unique_id] = (traccar_id, item)

        eligible_traccar_ids = {
            traccar_id
            for unique_id, (traccar_id, _item) in traccar_by_imei.items()
            if unique_id in sana_by_imei
        }

        # Traccar normally returns one latest position per device. Keep the
        # newest server-received point if an API/proxy ever returns duplicates.
        # Ignore every Traccar device outside this user's authorized SANA set.
        position_by_traccar_id = {}
        for position in traccar_positions:
            try:
                traccar_id = int(position.get('deviceId'))
            except (TypeError, ValueError):
                continue
            if traccar_id not in eligible_traccar_ids:
                continue
            received_at = traccar_position_timestamp(position)
            if received_at is not None and timezone.is_naive(received_at):
                received_at = timezone.make_aware(received_at)
            previous = position_by_traccar_id.get(traccar_id)
            previous_at = traccar_position_timestamp(previous) if previous else None
            if previous_at is not None and timezone.is_naive(previous_at):
                previous_at = timezone.make_aware(previous_at)
            if previous is None or (
                received_at is not None and (previous_at is None or received_at > previous_at)
            ):
                position_by_traccar_id[traccar_id] = position

        matched_position_ids = []
        for position in position_by_traccar_id.values():
            try:
                matched_position_ids.append(int(position['id']))
            except (KeyError, TypeError, ValueError):
                continue

        matches = {}
        if matched_position_ids:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT traccar_position_id, matched_latitude, matched_longitude, match_provider, matched_at
                    FROM gps.map_matched_position
                    WHERE traccar_position_id = ANY(%s)
                    """,
                    [matched_position_ids],
                )
                matches = {
                    int(row[0]): {
                        'latitude': float(row[1]),
                        'longitude': float(row[2]),
                        'provider': row[3],
                        'matched_at': row[4].isoformat() if row[4] else None,
                    }
                    for row in cursor.fetchall()
                }

        now = timezone.now()
        output = []
        for device in devices:
            traccar_link = traccar_by_imei.get(str(device.imei).strip())
            traccar_id, traccar_device = traccar_link if traccar_link else (None, None)
            position = position_by_traccar_id.get(traccar_id) if traccar_id is not None else None

            server_received_at = traccar_position_timestamp(position) if position else None
            if server_received_at is None and traccar_device:
                server_received_at = parse_datetime(str(traccar_device.get('lastUpdate') or ''))
            if server_received_at is not None and timezone.is_naive(server_received_at):
                server_received_at = timezone.make_aware(server_received_at)

            fresh = (
                server_received_at is not None
                and 0 <= (now - server_received_at).total_seconds() <= 300
            )
            traccar_status = str((traccar_device or {}).get('status') or '').lower()
            is_online = traccar_status == 'online' and fresh

            latitude = longitude = None
            position_id = None
            valid = False
            attributes = {}
            match = None
            speed_kmh = None
            heading = None
            device_time = None

            if position:
                try:
                    position_id = int(position['id'])
                    raw_latitude = float(position.get('latitude'))
                    raw_longitude = float(position.get('longitude'))
                    if (
                        math.isfinite(raw_latitude) and math.isfinite(raw_longitude)
                        and -90 <= raw_latitude <= 90
                        and -180 <= raw_longitude <= 180
                    ):
                        latitude, longitude = raw_latitude, raw_longitude
                except (KeyError, TypeError, ValueError, OverflowError):
                    pass

                attributes = position.get('attributes') if isinstance(position.get('attributes'), dict) else {}
                valid = bool(position.get('valid', True))
                try:
                    speed_kmh = round(float(position.get('speed') or 0) * 1.852, 1)
                except (TypeError, ValueError, OverflowError):
                    speed_kmh = None
                heading = position.get('course')
                device_time = position.get('fixTime') or position.get('deviceTime')
                match = matches.get(position_id) if position_id is not None else None
                if match:
                    latitude, longitude = match['latitude'], match['longitude']

            has_position = latitude is not None and longitude is not None
            if not traccar_device:
                status = 'unknown'
            elif traccar_status == 'offline' or (server_received_at is not None and not fresh):
                status = 'offline'
            elif traccar_status != 'online' or not is_online or not has_position:
                status = 'unknown'
            else:
                motion = attributes.get('motion')
                status = 'moving' if motion is True or (speed_kmh is not None and speed_kmh >= 3) else 'stopped'

            output.append({
                'device_id': device.pk,
                'imei': device.imei,
                'phone': (traccar_device or {}).get('phone'),
                'vehicle_id': device.vehicle_id,
                'vehicle_plate': device.vehicle.plate if device.vehicle_id else None,
                'latitude': latitude,
                'longitude': longitude,
                'has_position': has_position,
                'position_is_current': valid if position else False,
                'position_is_matched': match is not None,
                'match_provider': match['provider'] if match else None,
                'matched_at': match['matched_at'] if match else None,
                'speed': speed_kmh,
                'heading': heading,
                'last_seen': server_received_at.isoformat() if server_received_at else None,
                'device_time': device_time,
                'attributes': attributes,
                'traccar_status': traccar_status or None,
                'status': status,
            })

        output.sort(key=lambda item: item['device_id'])
        return Response(output)

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsSiteAdmin()]
        return super().get_permissions()

    def destroy(self, request, *args, **kwargs):
        """Permanently delete a device after explicit IMEI confirmation."""
        instance = self.get_object()
        confirmed_imei = request.data.get('confirm_imei')
        if confirmed_imei != instance.imei:
            return Response(
                {'detail': 'برای حذف دستگاه، IMEI را دقیقاً در confirm_imei ارسال کن.'},
                status=400,
            )
        with transaction.atomic():
            # GPS raw telemetry is owned by Traccar; SANA has no GPS purge function.
            # Remove operations referencing this device before deleting the fleet record.
            DeviceOperation.objects.filter(
                Q(device=instance) | Q(replacement_device=instance)
            ).delete()
            instance.delete()

        return Response(status=204)


class DriverViewSet(viewsets.ModelViewSet):
    queryset = Driver.objects.select_related('organization', 'branch').all()
    serializer_class = DriverSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['first_name', 'last_name', 'mobile', 'personnel_code']
    ordering_fields = ['last_name', 'created_at']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsOrganizationMember()]
        return super().get_permissions()

    def get_queryset(self):
        user = self.request.user
        qs = Driver.objects.select_related('organization', 'branch')

        if user.is_site_admin:
            pass
        elif user.is_main_user and user.organization:
            qs = qs.filter(organization=user.organization)
        elif user.is_branch_manager and user.branch:
            qs = qs.filter(branch=user.branch)
        else:
            qs = qs.none()

        # فیلترها
        branch = self.request.query_params.get('branch')
        if branch:
            qs = qs.filter(branch_id=branch)

        return qs


class DriverVehicleAssignmentViewSet(viewsets.ModelViewSet):
    """تاریخچه و مدیریت تخصیص راننده به خودرو."""
    queryset = DriverVehicleAssignment.objects.select_related(
        'driver', 'driver__organization', 'driver__branch',
        'vehicle', 'vehicle__organization', 'vehicle__branch',
    ).all()
    serializer_class = DriverVehicleAssignmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['started_at', 'ended_at', 'created_at']

    def get_queryset(self):
        user = self.request.user
        qs = self.queryset
        if user.is_site_admin:
            pass
        elif user.is_main_user and user.organization_id:
            qs = qs.filter(driver__organization_id=user.organization_id)
        elif user.is_branch_manager and user.branch_id:
            qs = qs.filter(driver__organization_id=user.organization_id, driver__branch_id=user.branch_id)
        else:
            qs = qs.none()

        driver = self.request.query_params.get('driver')
        vehicle = self.request.query_params.get('vehicle')
        active = self.request.query_params.get('active')

        if driver:
            qs = qs.filter(driver_id=driver)
        if vehicle:
            qs = qs.filter(vehicle_id=vehicle)
        if active == 'true':
            qs = qs.filter(ended_at__isnull=True)

        return qs

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsOrganizationMember()]
        return super().get_permissions()


class DeviceLifecycleEventViewSet(viewsets.ModelViewSet):
    """تاریخچه و ثبت رویدادهای چرخه عمر دستگاه."""
    queryset = DeviceLifecycleEvent.objects.select_related(
        'device', 'subscription', 'organization', 'user', 'vehicle', 'branch', 'performed_by'
    ).all()
    serializer_class = DeviceLifecycleEventSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['event_date', 'created_at']

    def get_queryset(self):
        user = self.request.user
        qs = self.queryset
        if user.is_site_admin:
            pass
        elif user.is_main_user and user.organization_id:
            access = DeviceCustomerAccessPeriod.objects.filter(device=OuterRef('device_id'), organization_id=user.organization_id, started_at__lte=OuterRef('event_date')).filter(Q(ended_at__isnull=True) | Q(ended_at__gte=OuterRef('event_date')))
            qs = qs.filter(Exists(access))
        elif user.is_branch_manager and user.branch_id:
            access = DeviceCustomerAccessPeriod.objects.filter(device=OuterRef('device_id'), organization_id=user.organization_id, branch_id=user.branch_id, started_at__lte=OuterRef('event_date')).filter(Q(ended_at__isnull=True) | Q(ended_at__gte=OuterRef('event_date')))
            qs = qs.filter(Exists(access))
        elif user.is_personal_user:
            # A personal customer may see lifecycle events from either an
            # access period or a subscription-device assignment that covered
            # the event timestamp. Keep this historical check independent
            # from the subscription's current status.
            access = DeviceCustomerAccessPeriod.objects.filter(
                device=OuterRef('device_id'),
                user_id=user.id,
                started_at__lte=OuterRef('event_date'),
            ).filter(
                Q(ended_at__isnull=True) | Q(ended_at__gte=OuterRef('event_date'))
            )
            contract_access = SubscriptionDevice.objects.filter(
                device=OuterRef('device_id'),
                subscription__user_id=user.id,
                subscription__start_date__lte=OuterRef('event_date__date'),
                subscription__end_date__gte=OuterRef('event_date__date'),
                start_date__lte=OuterRef('event_date__date'),
                end_date__gte=OuterRef('event_date__date'),
                assigned_at__lte=OuterRef('event_date'),
            ).filter(
                Q(unassigned_at__isnull=True)
                | Q(unassigned_at__gte=OuterRef('event_date'))
            )
            qs = qs.filter(Exists(access) | Exists(contract_access))
        else:
            qs = qs.none()

        device = self.request.query_params.get('device')
        if device:
            qs = qs.filter(device_id=device)
        event_type = self.request.query_params.get('event_type')
        if event_type:
            qs = qs.filter(event_type=event_type)
        return qs

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsSiteAdmin()]
        return super().get_permissions()


class DeviceReplacementRelationViewSet(viewsets.ModelViewSet):
    """رابطه‌های جایگزینی دستگاه‌ها؛ تغییر/ثبت فقط توسط ادمین سایت."""
    queryset = DeviceReplacementRelation.objects.select_related('source_device', 'replacement_device').all()
    serializer_class = DeviceReplacementRelationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['replacement_date', 'created_at']

    def get_queryset(self):
        user = self.request.user
        qs = self.queryset
        if user.is_site_admin:
            pass
        elif user.organization_id:
            qs = qs.filter(
                source_device__organization_id=user.organization_id
            ) | qs.filter(
                replacement_device__organization_id=user.organization_id
            )
        elif user.is_personal_user:
            qs = qs.filter(
                source_device__owner_user_id=user.id
            ) | qs.filter(
                replacement_device__owner_user_id=user.id
            )
        else:
            qs = qs.none()
        device = self.request.query_params.get('device')
        if device:
            qs = qs.filter(source_device_id=device) | qs.filter(replacement_device_id=device)
        return qs.distinct()

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsSiteAdmin()]
        return super().get_permissions()


class DeviceOperationViewSet(viewsets.ModelViewSet):
    """عملیات واقعی دستگاه؛ اجرای تغییرات فقط توسط ادمین سایت."""
    queryset = DeviceOperation.objects.select_related(
        'device', 'replacement_device', 'subscription', 'target_subscription',
        'target_organization', 'target_user', 'target_branch', 'target_vehicle', 'performed_by'
    ).all()
    serializer_class = DeviceOperationSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        user = self.request.user
        qs = self.queryset
        if user.is_site_admin:
            pass
        elif user.is_main_user and user.organization_id:
            access = DeviceCustomerAccessPeriod.objects.filter(device=OuterRef('device_id'), organization_id=user.organization_id, started_at__lte=OuterRef('performed_at')).filter(Q(ended_at__isnull=True) | Q(ended_at__gte=OuterRef('performed_at')))
            qs = qs.filter(Exists(access))
        elif user.is_branch_manager and user.branch_id:
            access = DeviceCustomerAccessPeriod.objects.filter(device=OuterRef('device_id'), organization_id=user.organization_id, branch_id=user.branch_id, started_at__lte=OuterRef('performed_at')).filter(Q(ended_at__isnull=True) | Q(ended_at__gte=OuterRef('performed_at')))
            qs = qs.filter(Exists(access))
        elif user.is_personal_user:
            access = DeviceCustomerAccessPeriod.objects.filter(device=OuterRef('device_id'), user_id=user.id, started_at__lte=OuterRef('performed_at')).filter(Q(ended_at__isnull=True) | Q(ended_at__gte=OuterRef('performed_at')))
            qs = qs.filter(Exists(access))
        else:
            qs = qs.none()
        device = self.request.query_params.get('device')
        if device:
            qs = qs.filter(device_id=device) | qs.filter(replacement_device_id=device)
        return qs.distinct()

    def get_permissions(self):
        if self.action == 'create':
            return [IsSiteAdmin()]
        return super().get_permissions()
