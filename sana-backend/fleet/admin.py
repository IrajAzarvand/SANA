from django.contrib import admin
from .models import VehicleType, Vehicle, Device, Driver, DeviceBranchHistory


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
        'imei', 'device_model', 'protocol', 'get_legal_owner', 'get_current_holder',
        'vehicle', 'management_status', 'created_at',
    ]
    list_filter = ['management_status', 'protocol']
    search_fields = ['imei', 'sim_number', 'device_model__manufacturer', 'device_model__name']
    ordering = ['-created_at']
    raw_id_fields = ['organization', 'owner_user', 'current_holder_organization', 'current_holder_user', 'branch', 'vehicle']
    # Ownership, holder, branch and vehicle changes must pass through audited
    # lifecycle operations, not direct Django-admin edits.
    readonly_fields = [
        'organization', 'owner_user',
        'current_holder_organization', 'current_holder_user',
        'branch', 'vehicle', 'management_status',
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_legal_owner(self, obj):
        if obj.organization:
            return obj.organization.name
        if obj.owner_user:
            return obj.owner_user.full_name or obj.owner_user.username
        return '—'
    get_legal_owner.short_description = 'مالک قانونی'

    def get_current_holder(self, obj):
        if obj.current_holder_organization:
            return obj.current_holder_organization.name
        if obj.current_holder_user:
            return obj.current_holder_user.full_name or obj.current_holder_user.username
        return '—'
    get_current_holder.short_description = 'مشتری / دارنده فعلی'


@admin.register(DeviceBranchHistory)
class DeviceBranchHistoryAdmin(admin.ModelAdmin):
    list_display = ['device', 'organization', 'branch', 'subscription', 'started_at', 'ended_at', 'reason']
    list_filter = ['organization', 'branch', 'reason']
    search_fields = ['device__imei', 'organization__name', 'branch__name', 'subscription__contract_number']
    raw_id_fields = ['device', 'organization', 'branch', 'subscription']
    ordering = ['-started_at']
    readonly_fields = [field.name for field in DeviceBranchHistory._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

