from django.conf import settings
from django.db import models
from django.utils import timezone


class ReferenceSource(models.Model):
    class SourceType(models.TextChoices):
        MANUFACTURER = "manufacturer", "مستندات سازنده"
        REPOSITORY = "repository", "مخزن کد"
        PROTOCOL_DOCS = "protocol_docs", "مستندات پروتکل"
        COMMUNITY = "community", "انجمن فنی"
        OTHER = "other", "سایر"

    name = models.CharField(max_length=160)
    base_url = models.URLField(max_length=1000)
    source_type = models.CharField(max_length=24, choices=SourceType.choices, default=SourceType.OTHER)
    enabled = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    configuration = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="decoder_reference_sources",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "id")
        constraints = [
            models.UniqueConstraint(fields=("name", "base_url"), name="decoder_source_name_url_uniq"),
        ]

    def __str__(self):
        return f"{self.name} ({self.base_url})"


class DiscoveryCase(models.Model):
    class Status(models.TextChoices):
        PENDING_SEARCH = "pending_search", "در انتظار جست‌وجو"
        SEARCHING = "searching", "در حال جست‌وجو"
        CANDIDATES_FOUND = "candidates_found", "نامزد پیدا شد"
        UNRESOLVED = "unresolved", "حل‌نشده"
        NEEDS_REVIEW = "needs_review", "نیازمند بررسی ادمین"
        CLOSED = "closed", "بسته‌شده"

    identifier_candidate = models.CharField(max_length=128, blank=True, db_index=True)
    protocol_hint = models.CharField(max_length=80, blank=True)
    device_model_hint = models.CharField(max_length=160, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING_SEARCH, db_index=True)
    raw_sample_count = models.PositiveIntegerField(default=0)
    queue_references = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    last_searched_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at", "-id")
        indexes = [
            models.Index(fields=("status", "updated_at"), name="decoder_case_status_updated"),
        ]

    def __str__(self):
        return f"Discovery #{self.pk or 'new'} — {self.identifier_candidate or 'شناسه نامشخص'}"


class DecoderCandidate(models.Model):
    class Status(models.TextChoices):
        DISCOVERED = "discovered", "کشف‌شده"
        ARCHIVED = "archived", "آرشیو شده"
        TESTING = "testing", "در حال آزمون"
        COMPATIBLE_PENDING_APPROVAL = "compatible_pending_approval", "سازگار؛ منتظر تأیید"
        INCOMPATIBLE_NEEDS_ADAPTATION = "incompatible_needs_adaptation", "ناسازگار؛ نیازمند تطبیق"
        FAILED_REVIEW_REQUIRED = "failed_review_required", "آزمون ناموفق؛ نیازمند بررسی"
        ADAPTED_TESTING = "adapted_testing", "نسخه تطبیق‌یافته در حال آزمون"
        PUBLISHED = "published", "منتشرشده"
        REJECTED = "rejected", "ردشده با حفظ سوابق"

    class Compatibility(models.TextChoices):
        UNKNOWN = "unknown", "نامشخص"
        DIRECT = "direct", "قابل اجرا مستقیم"
        INCOMPATIBLE = "incompatible", "ناسازگار"
        UNCERTAIN = "uncertain", "نیازمند بررسی بیشتر"

    class LicenseStatus(models.TextChoices):
        UNKNOWN = "unknown", "نامشخص"
        PERMITTED = "permitted", "نگهداری مجاز"
        RESTRICTED = "restricted", "دارای محدودیت"
        PROHIBITED = "prohibited", "ذخیره/بازتوزیع ممنوع"

    case = models.ForeignKey(DiscoveryCase, on_delete=models.CASCADE, related_name="candidates")
    source = models.ForeignKey(
        ReferenceSource, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="decoder_candidates",
    )
    title = models.CharField(max_length=240)
    source_url = models.URLField(max_length=2000)
    source_revision = models.CharField(max_length=240, blank=True)
    artifact_name = models.CharField(max_length=500, blank=True)
    artifact_storage_key = models.CharField(max_length=1000, blank=True)
    artifact_sha256 = models.CharField(max_length=64, blank=True, db_index=True)
    artifact_size_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    artifact_preserved = models.BooleanField(default=False)
    language = models.CharField(max_length=80, blank=True)
    runtime = models.CharField(max_length=120, blank=True)
    dependencies = models.JSONField(default=list, blank=True)
    license_identifier = models.CharField(max_length=120, blank=True)
    license_status = models.CharField(
        max_length=16, choices=LicenseStatus.choices, default=LicenseStatus.UNKNOWN,
    )
    compatibility = models.CharField(
        max_length=16, choices=Compatibility.choices, default=Compatibility.UNKNOWN,
    )
    status = models.CharField(max_length=40, choices=Status.choices, default=Status.DISCOVERED, db_index=True)
    incompatibility_reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    discovered_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-discovered_at", "-id")
        indexes = [
            models.Index(fields=("case", "status"), name="decoder_candidate_case_status"),
            models.Index(fields=("compatibility", "status"), name="decoder_candidate_compat_status"),
        ]

    def __str__(self):
        return self.title


class CandidateTestRun(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار اجرا"
        RUNNING = "running", "در حال اجرا"
        PASSED = "passed", "موفق"
        FAILED = "failed", "ناموفق"
        ERROR = "error", "خطای اجرا"
        BLOCKED = "blocked", "مسدودشده به دلایل امنیتی"

    candidate = models.ForeignKey(DecoderCandidate, on_delete=models.CASCADE, related_name="test_runs")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    runner_version = models.CharField(max_length=80, blank=True)
    sample_count = models.PositiveIntegerField(default=0)
    report = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="decoder_candidate_test_runs",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")

    def __str__(self):
        return f"Test #{self.pk or 'new'} — {self.candidate}"


class PublishedDecoderVersion(models.Model):
    candidate = models.ForeignKey(DecoderCandidate, on_delete=models.PROTECT, related_name="published_versions")
    protocol = models.CharField(max_length=80, db_index=True)
    version = models.PositiveIntegerField()
    decoder_path = models.CharField(max_length=1000)
    is_active = models.BooleanField(default=False, db_index=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="approved_decoder_versions",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    rollback_reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("protocol", "-version")
        constraints = [
            models.UniqueConstraint(fields=("protocol", "version"), name="decoder_protocol_version_uniq"),
        ]

    def __str__(self):
        return f"{self.protocol} v{self.version}"
