from django.contrib import admin

from .models import (
    CandidateTestRun,
    DecoderCandidate,
    DiscoveryCase,
    PublishedDecoderVersion,
    ReferenceSource,
)


class SiteAdminOnlyModelAdmin(admin.ModelAdmin):
    """Restrict discovery records to the global site administrator."""

    def has_module_permission(self, request):
        return bool(request.user.is_authenticated and getattr(request.user, "is_site_admin", False))

    def has_view_permission(self, request, obj=None):
        return bool(request.user.is_authenticated and getattr(request.user, "is_site_admin", False))

    def has_add_permission(self, request):
        return bool(request.user.is_authenticated and getattr(request.user, "is_site_admin", False))

    def has_change_permission(self, request, obj=None):
        return bool(request.user.is_authenticated and getattr(request.user, "is_site_admin", False))

    def has_delete_permission(self, request, obj=None):
        # Keep discovery evidence and candidate history; disable rather than delete records.
        return False


@admin.register(ReferenceSource)
class ReferenceSourceAdmin(SiteAdminOnlyModelAdmin):
    list_display = ("name", "source_type", "enabled", "base_url", "updated_at")
    list_filter = ("source_type", "enabled")
    search_fields = ("name", "base_url")
    readonly_fields = ("created_at", "updated_at")


@admin.register(DiscoveryCase)
class DiscoveryCaseAdmin(SiteAdminOnlyModelAdmin):
    list_display = ("id", "identifier_candidate", "protocol_hint", "status", "raw_sample_count", "updated_at")
    list_filter = ("status",)
    search_fields = ("identifier_candidate", "protocol_hint", "device_model_hint")
    readonly_fields = ("created_at", "updated_at", "last_searched_at")


@admin.register(DecoderCandidate)
class DecoderCandidateAdmin(SiteAdminOnlyModelAdmin):
    list_display = ("id", "title", "case", "status", "compatibility", "license_status", "discovered_at")
    list_filter = ("status", "compatibility", "license_status", "language")
    search_fields = ("title", "source_url", "artifact_sha256", "case__identifier_candidate")
    readonly_fields = ("artifact_sha256", "artifact_size_bytes", "discovered_at", "created_at", "updated_at")


@admin.register(CandidateTestRun)
class CandidateTestRunAdmin(SiteAdminOnlyModelAdmin):
    list_display = ("id", "candidate", "status", "sample_count", "created_at", "finished_at")
    list_filter = ("status",)
    readonly_fields = ("created_at",)


@admin.register(PublishedDecoderVersion)
class PublishedDecoderVersionAdmin(SiteAdminOnlyModelAdmin):
    list_display = ("protocol", "version", "is_active", "candidate", "approved_by", "published_at")
    list_filter = ("protocol", "is_active")
    readonly_fields = ("created_at",)
