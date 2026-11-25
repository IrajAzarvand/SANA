from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, UserSession


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'full_name', 'role', 'account_type', 'organization', 'branch', 'is_active']
    list_filter = ['role', 'account_type', 'is_active', 'organization']
    search_fields = ['username', 'first_name', 'last_name', 'email', 'mobile']
    ordering = ['-date_joined']

    def has_delete_permission(self, request, obj=None):
        # Account deletion must go through the archive lifecycle so historical
        # contracts, ownership, and audit references remain intact.
        return False

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('اطلاعات شخصی', {'fields': ('first_name', 'last_name', 'email', 'mobile', 'national_id')}),
        ('نقش و دسترسی', {'fields': ('account_type', 'role', 'organization', 'branch', 'is_active', 'is_staff', 'is_superuser')}),
        ('تاریخ‌ها', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'role', 'account_type', 'organization', 'branch'),
        }),
    )

@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ['user', 'created_at', 'last_activity_at', 'expires_at', 'revoked_at', 'ip_address']
    list_filter = ['revoked_at', 'created_at']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'ip_address']
    readonly_fields = [
        'id', 'user', 'created_at', 'last_activity_at', 'expires_at',
        'revoked_at', 'current_refresh_jti', 'ip_address', 'user_agent',
    ]
    ordering = ['-created_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
