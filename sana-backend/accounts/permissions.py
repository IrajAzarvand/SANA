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
    """فقط کاربران سازمانی (Main User یا Branch Manager)"""

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.account_type == 'organization'
        )