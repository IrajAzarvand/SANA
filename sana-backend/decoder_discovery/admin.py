from django.contrib import admin

from .models import (
    CandidateTestRun,
    DecoderCandidate,
    DiscoveryCase,
    PublishedDecoderVersion,
    ReferenceSource,
)


@admin.register(ReferenceSource)
class ReferenceSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "source_type", "enabled", "base_url", "updated_at")
    list_filter = ("source_type", "enabled")
    search_fields = ("name", "base_url")
    readonly_fields = ("created_at", "updated_at")


@admin.register(DiscoveryCase)
class DiscoveryCaseAdmin(admin.ModelAdmin):
    list_display = ("id", "identifier_candidate", "protocol_hint", "status", "raw_sample_count", "updated_at")
    list_filter = ("status",)
    search_fields = ("identifier_candidate", "protocol_hint", "device_model_hint")
    readonly_fields = ("created_at", "updated_at", "last_searched_at")


@admin.register(DecoderCandidate)
class DecoderCandidateAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "case", "status", "compatibility", "license_status", "discovered_at")
    list_filter = ("status", "compatibility", "license_status", "language")
    search_fields = ("title", "source_url", "artifact_sha256", "case__identifier_candidate")
    readonly_fields = ("artifact_sha256", "artifact_size_bytes", "discovered_at", "created_at", "updated_at")


@admin.register(CandidateTestRun)
class CandidateTestRunAdmin(admin.ModelAdmin):
    list_display = ("id", "candidate", "status", "sample_count", "created_at", "finished_at")
    list_filter = ("status",)
    readonly_fields = ("created_at",)


@admin.register(PublishedDecoderVersion)
class PublishedDecoderVersionAdmin(admin.ModelAdmin):
    list_display = ("protocol", "version", "is_active", "candidate", "approved_by", "published_at")
    list_filter = ("protocol", "is_active")
    readonly_fields = ("created_at",)
