from django.utils import timezone
from django.utils.dateparse import parse_datetime
from datetime import datetime, time as datetime_time
from django.db import connection, transaction
from django.db.models import Exists, OuterRef, Prefetch, Q
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import VehicleType, Vehicle, DeviceModel, Device, Driver, DeviceLifecycleEvent, DeviceReplacementRelation, DeviceOperation, DeviceCustomerAccessPeriod, DriverVehicleAssignment
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
from .traccar_api import TraccarAPIError, traccar_current_positions, traccar_device_positions, traccar_devices


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
        ).prefetch_related(
            Prefetch(
                'replacement_relations_as_source',
                queryset=DeviceReplacementRelation.objects.select_related('replacement_device').order_by('-replacement_date', '-id'),
                to_attr='_replacement_relations_as_source',
            ),
            Prefetch(
                'replacement_relations_as_replacement',
                queryset=DeviceReplacementRelation.objects.select_related('source_device').order_by('-replacement_date', '-id'),
                to_attr='_replacement_relations_as_replacement',
            ),
        )

        if user.is_site_admin:
            pass
        elif user.is_main_user and user.organization:
            qs = qs.filter(customer_access_periods__organization=user.organization, customer_access_periods__ended_at__isnull=True).distinct()
        elif user.is_branch_manager and user.branch:
            qs = qs.filter(customer_access_periods__organization=user.organization, customer_access_periods__branch=user.branch, customer_access_periods__ended_at__isnull=True).distinct()
        elif user.is_personal_user:
            qs = qs.filter(customer_access_periods__user=user, customer_access_periods__ended_at__isnull=True).distinct()
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

    def list(self, request, *args, **kwargs):
        """List devices and enrich the page with GPS state using the same DB login."""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        devices = list(page if page is not None else queryset)

        # Traccar owns last-seen timestamps; SANA does not keep a GPS current-state copy.
        for device in devices:
            device.last_data_received_at = None
        try:
            traccar_by_imei = {
                str(item.get('uniqueId') or '').strip(): item
                for item in traccar_devices()
                if str(item.get('uniqueId') or '').strip()
            }
            for device in devices:
                traccar_device = traccar_by_imei.get(str(device.imei).strip())
                last_update = traccar_device.get('lastUpdate') if traccar_device else None
                device.last_data_received_at = parse_datetime(last_update) if last_update else None
        except TraccarAPIError:
            # The device list remains available during a temporary Traccar outage.
            pass

        serializer = self.get_serializer(devices, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='report-history')
    def report_history(self, request):
        """Return authorized device history for map playback; customer dates are contract-bounded."""
        device_id = request.query_params.get('device_id')
        if not device_id:
            return Response({'detail': 'انتخاب دستگاه الزامی است.'}, status=400)

        device = self.get_queryset().filter(pk=device_id).select_related('vehicle').first()
        if device is None:
            return Response({'detail': 'دستگاه یافت نشد یا مجوز مشاهده آن را ندارید.'}, status=404)

        range_start = range_end = None
        if not request.user.is_site_admin:
            links = list(
                SubscriptionDevice.objects.filter(
                    device=device,
                    unassigned_at__isnull=True,
                    subscription__status__in=['active', 'expired'],
                ).select_related('subscription').order_by('-start_date', '-id')
            )
            access_query = DeviceCustomerAccessPeriod.objects.filter(
                device=device, ended_at__isnull=True,
            )
            if request.user.is_personal_user:
                access_query = access_query.filter(user=request.user)
                links = [link for link in links if link.subscription.user_id == request.user.pk]
            elif request.user.is_branch_manager:
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
            cursor_time = parse_datetime(request.query_params.get('cursor_time', ''))
            cursor_id = int(request.query_params.get('cursor_id', '0'))
        except (TypeError, ValueError):
            return Response({'detail': 'نشانگر صفحه‌بندی نامعتبر است.'}, status=400)
        if cursor_time is not None and timezone.is_naive(cursor_time):
            cursor_time = timezone.make_aware(cursor_time)

        limit = 5000
        try:
            traccar_device = next(
                (
                    item for item in traccar_devices()
                    if str(item.get('uniqueId') or '').strip() == str(device.imei).strip()
                ),
                None,
            )
            if traccar_device is None or traccar_device.get('id') is None:
                return Response({'detail': 'دستگاه در Traccar ثبت نشده است.'}, status=404)
            positions = traccar_device_positions(
                int(traccar_device['id']),
                raw_start.isoformat().replace('+00:00', 'Z'),
                raw_end.isoformat().replace('+00:00', 'Z'),
            )
        except TraccarAPIError:
            return Response({'detail': 'دریافت تاریخچه از Traccar موقتاً ممکن نیست.'}, status=503)

        positions = []
        # (The actual API response is assigned separately to avoid shadowing the name.)
        try:
            positions = traccar_device_positions(
                int(traccar_device['id']),
                raw_start.isoformat().replace('+00:00', 'Z'),
                raw_end.isoformat().replace('+00:00', 'Z'),
            )
        except TraccarAPIError:
            return Response({'detail': 'دریافت تاریخچه از Traccar موقتاً ممکن نیست.'}, status=503)

        normalized = []
        for item in positions:
            try:
                point_id = int(item['id'])
                point_time = parse_datetime(item.get('fixTime') or item.get('deviceTime') or item.get('serverTime') or '')
                latitude = float(item['latitude'])
                longitude = float(item['longitude'])
            except (KeyError, TypeError, ValueError):
                continue
            if point_time is None:
                continue
            if timezone.is_naive(point_time):
                point_time = timezone.make_aware(point_time)
            if cursor_time is not None and cursor_id > 0 and (point_time, point_id) <= (cursor_time, cursor_id):
                continue
            normalized.append((point_time, point_id, item, latitude, longitude))
        normalized.sort(key=lambda row: (row[0], row[1]))
        has_more = len(normalized) > limit
        normalized = normalized[:limit]
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

        next_cursor = None
        if has_more and points:
            last = points[-1]
            next_cursor = {'cursor_time': last['device_time'], 'cursor_id': last['id']}
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

    @action(detail=False, methods=['post'], url_path='map-matching-activity')
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
                    INSERT INTO gps.map_matching_watchers
                        (session_id, user_id, expires_at, updated_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP + INTERVAL '45 seconds', CURRENT_TIMESTAMP)
                    ON CONFLICT (session_id) DO UPDATE
                    SET user_id = EXCLUDED.user_id,
                        expires_at = EXCLUDED.expires_at,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    [session_id, request.user.pk],
                )
            else:
                cursor.execute(
                    "DELETE FROM gps.map_matching_watchers WHERE session_id = %s AND user_id = %s",
                    [session_id, request.user.pk],
                )
        return Response({'active': active})

    @action(detail=False, methods=['get'], url_path='map-positions')
    def map_positions(self, request):
        """Return live positions from Traccar; only Neshan match overlays come from SANA."""
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

        traccar_by_id = {
            int(item['id']): item
            for item in traccar_devices_list
            if item.get('id') is not None
        }
        eligible = {}
        for traccar_id, traccar_device in traccar_by_id.items():
            unique_id = str(traccar_device.get('uniqueId') or '').strip()
            sana_device = sana_by_imei.get(unique_id)
            if sana_device is not None:
                eligible[traccar_id] = (sana_device, traccar_device)

        current = []
        for position in traccar_positions:
            try:
                traccar_id = int(position['deviceId'])
                position_id = int(position['id'])
                latitude = float(position['latitude'])
                longitude = float(position['longitude'])
            except (KeyError, TypeError, ValueError):
                continue
            if traccar_id not in eligible or not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                continue
            sana_device, traccar_device = eligible[traccar_id]
            current.append((position_id, traccar_id, sana_device, traccar_device, position, latitude, longitude))

        position_ids = [row[0] for row in current]
        matches = {}
        if position_ids:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT traccar_position_id, matched_latitude, matched_longitude, match_provider, matched_at
                    FROM gps.map_matched_position
                    WHERE traccar_position_id = ANY(%s)
                    """,
                    [position_ids],
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
        for position_id, traccar_id, device, traccar_device, position, latitude, longitude in current:
            last_update = parse_datetime(str(traccar_device.get('lastUpdate') or ''))
            if last_update is not None and timezone.is_naive(last_update):
                last_update = timezone.make_aware(last_update)
            is_online = (
                str(traccar_device.get('status') or '').lower() == 'online'
                and last_update is not None
                and (now - last_update).total_seconds() <= 300
            )
            attributes = position.get('attributes') if isinstance(position.get('attributes'), dict) else {}
            match = matches.get(position_id)
            valid = bool(position.get('valid', True))
            speed_kmh = float(position.get('speed') or 0) * 1.852
            motion = attributes.get('motion')
            status = 'offline' if not is_online else ('moving' if motion is True or speed_kmh >= 3 else 'stopped')
            output.append({
                'device_id': device.pk,
                'imei': device.imei,
                'vehicle_id': device.vehicle_id,
                'vehicle_plate': device.vehicle.plate if device.vehicle_id else None,
                'latitude': match['latitude'] if match else latitude,
                'longitude': match['longitude'] if match else longitude,
                'position_is_current': valid,
                'position_is_matched': match is not None,
                'match_provider': match['provider'] if match else None,
                'matched_at': match['matched_at'] if match else None,
                'speed': speed_kmh,
                'heading': position.get('course'),
                'last_seen': traccar_device.get('lastUpdate') or position.get('serverTime'),
                'device_time': position.get('fixTime') or position.get('deviceTime'),
                'status': status,
            })
        output.sort(key=lambda item: item['device_id'])
        return Response(output)

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsSiteAdmin()]
        return super().get_permissions()

    def destroy(self, request, *args, **kwargs):
        """Permanently delete a device and its related records only after explicit IMEI confirmation."""
        instance = self.get_object()
        confirmed_imei = request.data.get('confirm_imei')
        if confirmed_imei != instance.imei:
            return Response(
                {'detail': 'برای حذف دائمی، IMEI دستگاه باید دقیقاً تأیید شود.'},
                status=400,
            )

        with transaction.atomic():
            # SECURITY DEFINER function removes GPS-schema rows that reference this device.
            with connection.cursor() as cursor:
                cursor.execute('SELECT gps.purge_device_data(%s)', [instance.pk])
            # DeviceOperation protects its referenced devices from accidental deletion.
            # Explicitly remove operations where this device is either the subject or replacement.
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
            access = DeviceCustomerAccessPeriod.objects.filter(device=OuterRef('device_id'), user_id=user.id, started_at__lte=OuterRef('event_date')).filter(Q(ended_at__isnull=True) | Q(ended_at__gte=OuterRef('event_date')))
            qs = qs.filter(Exists(access))
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
