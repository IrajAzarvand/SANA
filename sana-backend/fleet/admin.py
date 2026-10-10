from django.contrib import admin
from .models import VehicleType, Vehicle, Device, Driver, GT06Position


# ═══════════════════════════════════════════════
# VehicleType و Vehicle و Driver از Admin حذف شدن
# چون مدیریتشون توسط خود مشتری (Frontend) انجام می‌شه
# ═══════════════════════════════════════════════

# @admin.register(VehicleType)
# @admin.register(Vehicle)
# @admin.register(Driver)


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = [
        'imei', 'protocol', 'get_customer',
        'vehicle', 'management_status', 'created_at',
    ]
    list_filter = ['management_status', 'protocol']
    search_fields = ['imei', 'sim_number']
    ordering = ['-created_at']
    raw_id_fields = ['organization', 'owner_user', 'branch', 'vehicle']

    def get_customer(self, obj):
        if obj.organization:
            return obj.organization.name
        if obj.owner_user:
            return obj.owner_user.full_name or obj.owner_user.username
        return '—'
    get_customer.short_description = 'مشتری'


@admin.register(GT06Position)
class GT06PositionAdmin(admin.ModelAdmin):
    list_display = [
        'device', 'gps_time', 'latitude', 'longitude',
        'speed_kmh', 'course', 'satellites', 'received_at',
    ]
    list_filter = ['received_at']
    search_fields = ['device__imei']
    ordering = ['-gps_time']
    readonly_fields = [
        'device', 'gps_time', 'latitude', 'longitude', 'speed_kmh',
        'course', 'satellites', 'raw_frame', 'received_at',
    ]
