from rest_framework import permissions


class IsSiteAdminOrReadOnly(permissions.BasePermission):
    """فقط ادمین کل سایت می‌تونه بنویسه"""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # خواندن برای همه کاربران لاگین‌شده
        if request.method in permissions.SAFE_METHODS:
            return True

        # نوشتن فقط برای ادمین
        return request.user.is_site_admin


class IsSiteAdmin(permissions.BasePermission):
    """فقط ادمین کل سایت"""

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.is_site_admin
        )


class IsMainUserOrSiteAdmin(permissions.BasePermission):
    """فقط Main User و ادمین کل سایت"""

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            (request.user.is_site_admin or request.user.is_main_user)
        )


class IsOrganizationMember(permissions.BasePermission):
    """کاربر سازمانی یا ادمین کل سایت"""

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            (request.user.is_site_admin or request.user.account_type == 'organization')
        )

class IsSiteAdminOrMainUser(permissions.BasePermission):
    """Only site administrators and organization owners may manage organization users."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated
            and (user.is_site_admin or user.is_main_user)
        )

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_site_admin:
            return True
        if not user.is_main_user or not user.organization_id:
            return False
        return (
            getattr(obj, 'organization_id', None) == user.organization_id
            or getattr(getattr(obj, 'branch', None), 'organization_id', None) == user.organization_id
        )
