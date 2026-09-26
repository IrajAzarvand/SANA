from django.contrib import admin
from .models import (
    Organization,
    Branch,
    Subscription,
    SubscriptionDevice,
    SubscriptionPayment,
)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'status', 'phone', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['name', 'code', 'registration_number']
    ordering = ['name']


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'organization', 'status', 'phone']
    list_filter = ['status', 'organization']
    search_fields = ['name', 'code']
    ordering = ['organization', 'name']


class SubscriptionDeviceInline(admin.TabularInline):
    model = SubscriptionDevice
    extra = 0
    raw_id_fields = ['device']
    fields = ['device', 'start_date', 'end_date', 'assigned_at', 'unassigned_at']
    readonly_fields = ['assigned_at', 'unassigned_at']


class SubscriptionPaymentInline(admin.TabularInline):
    model = SubscriptionPayment
    extra = 0
    fields = ['amount', 'payment_date', 'device_count', 'description']


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        'contract_number',
        'get_customer_name',
        'customer_type',
        'start_date',
        'end_date',
        'status',
        'price',
        'days_until_expiry_display',
    ]
    list_filter = ['status', 'customer_type', 'start_date', 'end_date']
    search_fields = ['contract_number', 'organization__name', 'user__username']
    ordering = ['-created_at']
    inlines = [SubscriptionDeviceInline, SubscriptionPaymentInline]
    raw_id_fields = ['organization', 'user']

    def days_until_expiry_display(self, obj):
        d = obj.days_until_expiry
        if d < 0:
            return f'منقضی ({abs(d)} روز پیش)'
        if d <= 30:
            return f'{d} روز (نزدیک)'
        return f'{d} روز'
    days_until_expiry_display.short_description = 'روز تا پایان'


@admin.register(SubscriptionDevice)
class SubscriptionDeviceAdmin(admin.ModelAdmin):
    list_display = [
        'subscription', 'device', 'start_date', 'end_date',
        'is_active', 'assigned_at', 'unassigned_at',
    ]
    list_filter = ['start_date', 'end_date', 'unassigned_at']
    search_fields = ['device__imei', 'subscription__contract_number']
    raw_id_fields = ['device', 'subscription']


@admin.register(SubscriptionPayment)
class SubscriptionPaymentAdmin(admin.ModelAdmin):
    list_display = ['subscription', 'amount', 'payment_date', 'device_count', 'created_at']
    list_filter = ['payment_date']
    search_fields = ['subscription__contract_number', 'description']
    raw_id_fields = ['subscription']