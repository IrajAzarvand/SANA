import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ReferenceSource",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160)),
                ("base_url", models.URLField(max_length=1000)),
                ("source_type", models.CharField(choices=[("manufacturer", "مستندات سازنده"), ("repository", "مخزن کد"), ("protocol_docs", "مستندات پروتکل"), ("community", "انجمن فنی"), ("other", "سایر")], default="other", max_length=24)),
                ("enabled", models.BooleanField(default=True)),
                ("notes", models.TextField(blank=True)),
                ("configuration", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="decoder_reference_sources", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("name", "id")},
        ),
        migrations.CreateModel(
            name="DiscoveryCase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("identifier_candidate", models.CharField(blank=True, db_index=True, max_length=128)),
                ("protocol_hint", models.CharField(blank=True, max_length=80)),
                ("device_model_hint", models.CharField(blank=True, max_length=160)),
                ("status", models.CharField(choices=[("pending_search", "در انتظار جست‌وجو"), ("searching", "در حال جست‌وجو"), ("candidates_found", "نامزد پیدا شد"), ("unresolved", "حل‌نشده"), ("needs_review", "نیازمند بررسی ادمین"), ("closed", "بسته‌شده")], db_index=True, default="pending_search", max_length=24)),
                ("raw_sample_count", models.PositiveIntegerField(default=0)),
                ("queue_references", models.JSONField(blank=True, default=list)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("last_searched_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("-updated_at", "-id")},
        ),
        migrations.CreateModel(
            name="DecoderCandidate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=240)),
                ("source_url", models.URLField(max_length=2000)),
                ("source_revision", models.CharField(blank=True, max_length=240)),
                ("artifact_name", models.CharField(blank=True, max_length=500)),
                ("artifact_storage_key", models.CharField(blank=True, max_length=1000)),
                ("artifact_sha256", models.CharField(blank=True, db_index=True, max_length=64)),
                ("artifact_size_bytes", models.PositiveBigIntegerField(blank=True, null=True)),
                ("artifact_preserved", models.BooleanField(default=False)),
                ("language", models.CharField(blank=True, max_length=80)),
                ("runtime", models.CharField(blank=True, max_length=120)),
                ("dependencies", models.JSONField(blank=True, default=list)),
                ("license_identifier", models.CharField(blank=True, max_length=120)),
                ("license_status", models.CharField(choices=[("unknown", "نامشخص"), ("permitted", "نگهداری مجاز"), ("restricted", "دارای محدودیت"), ("prohibited", "ذخیره/بازتوزیع ممنوع")], default="unknown", max_length=16)),
                ("compatibility", models.CharField(choices=[("unknown", "نامشخص"), ("direct", "قابل اجرا مستقیم"), ("incompatible", "ناسازگار"), ("uncertain", "نیازمند بررسی بیشتر")], default="unknown", max_length=16)),
                ("status", models.CharField(choices=[("discovered", "کشف‌شده"), ("archived", "آرشیو شده"), ("testing", "در حال آزمون"), ("compatible_pending_approval", "سازگار؛ منتظر تأیید"), ("incompatible_needs_adaptation", "ناسازگار؛ نیازمند تطبیق"), ("failed_review_required", "آزمون ناموفق؛ نیازمند بررسی"), ("adapted_testing", "نسخه تطبیق‌یافته در حال آزمون"), ("published", "منتشرشده"), ("rejected", "ردشده با حفظ سوابق")], db_index=True, default="discovered", max_length=40)),
                ("incompatibility_reason", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("discovered_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("case", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="candidates", to="decoder_discovery.discoverycase")),
                ("source", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="decoder_candidates", to="decoder_discovery.referencesource")),
            ],
            options={"ordering": ("-discovered_at", "-id")},
        ),
        migrations.CreateModel(
            name="CandidateTestRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("pending", "در انتظار اجرا"), ("running", "در حال اجرا"), ("passed", "موفق"), ("failed", "ناموفق"), ("error", "خطای اجرا"), ("blocked", "مسدودشده به دلایل امنیتی")], db_index=True, default="pending", max_length=12)),
                ("runner_version", models.CharField(blank=True, max_length=80)),
                ("sample_count", models.PositiveIntegerField(default=0)),
                ("report", models.JSONField(blank=True, default=dict)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("candidate", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="test_runs", to="decoder_discovery.decodercandidate")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="decoder_candidate_test_runs", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at", "-id")},
        ),
        migrations.CreateModel(
            name="PublishedDecoderVersion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("protocol", models.CharField(db_index=True, max_length=80)),
                ("version", models.PositiveIntegerField()),
                ("decoder_path", models.CharField(max_length=1000)),
                ("is_active", models.BooleanField(db_index=True, default=False)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("rollback_reason", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approved_decoder_versions", to=settings.AUTH_USER_MODEL)),
                ("candidate", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="published_versions", to="decoder_discovery.decodercandidate")),
            ],
            options={"ordering": ("protocol", "-version")},
        ),
        migrations.AddConstraint(
            model_name="referencesource",
            constraint=models.UniqueConstraint(fields=("name", "base_url"), name="decoder_source_name_url_uniq"),
        ),
        migrations.AddConstraint(
            model_name="publisheddecoderversion",
            constraint=models.UniqueConstraint(fields=("protocol", "version"), name="decoder_protocol_version_uniq"),
        ),
        migrations.AddIndex(
            model_name="discoverycase",
            index=models.Index(fields=["status", "updated_at"], name="decoder_case_status_updated"),
        ),
        migrations.AddIndex(
            model_name="decodercandidate",
            index=models.Index(fields=["case", "status"], name="decoder_candidate_case_status"),
        ),
        migrations.AddIndex(
            model_name="decodercandidate",
            index=models.Index(fields=["compatibility", "status"], name="decoder_candidate_compat_status"),
        ),
    ]
