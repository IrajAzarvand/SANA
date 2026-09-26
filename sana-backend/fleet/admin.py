from django.contrib import admin
from .models import VehicleType, Vehicle, DeviceModel, Device, Driver


# ═══════════════════════════════════════════════
# VehicleType و Vehicle و Driver از Admin حذف شدن
# چون مدیریتشون توسط خود مشتری (Frontend) انجام می‌شه
# ═══════════════════════════════════════════════

# @admin.register(VehicleType)
# @admin.register(Vehicle)
# @admin.register(Driver)


@admin.register(DeviceModel)
class DeviceModelAdmin(admin.ModelAdmin):
    list_display = ['manufacturer', 'name', 'code', 'protocol']
    list_filter = ['manufacturer', 'protocol']
    search_fields = ['name', 'code']


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = [
        'imei', 'device_model', 'get_customer',
        'vehicle', 'management_status', 'created_at',
    ]
    list_filter = ['management_status', 'device_model']
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