from __future__ import annotations

from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from fleet.models import UnknownGPSData

from decoder_discovery.models import DiscoveryCase, DiscoverySample
from decoder_discovery.sample_analysis import analyze_raw_payload


class Command(BaseCommand):
    help = (
        "Idempotently import raw unknown-GPS queue rows into protocol-neutral "
        "discovery cases and save sample fingerprints/features."
    )

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=500)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report eligible rows without writing discovery records.",
        )

    def handle(self, *args, **options):
        limit = max(1, min(options["limit"], 10000))
        rows = list(
            UnknownGPSData.objects.filter(status__in=("pending", "matched", "failed"))
            .order_by("id")[:limit]
        )
        grouped = defaultdict(list)
        for row in rows:
            grouped[row.session_id].append(row)

        if options["dry_run"]:
            already_imported = DiscoverySample.objects.filter(
                queue_row_id__in=[row.pk for row in rows]
            ).count()
            self.stdout.write(
                f"dry_run=true rows={len(rows)} sessions={len(grouped)} "
                f"already_imported={already_imported}"
            )
            return

        created_samples = 0
        created_cases = 0
        for session_id, session_rows in grouped.items():
            session_identifier = next(
                (row.identifier_candidate for row in session_rows if row.identifier_candidate),
                "",
            )
            with transaction.atomic():
                case, case_created = DiscoveryCase.objects.get_or_create(
                    queue_session_id=session_id,
                    defaults={
                        "identifier_candidate": session_identifier,
                        "status": DiscoveryCase.Status.PENDING_SEARCH,
                        "metadata": {
                            "intake": "unknown_gps_queue",
                            "protocol_assigned_by_intake": False,
                        },
                    },
                )
                created_cases += int(case_created)

                if session_identifier and not case.identifier_candidate:
                    case.identifier_candidate = session_identifier
                    case.save(update_fields=("identifier_candidate", "updated_at"))

                for row in session_rows:
                    payload = bytes(row.raw_payload)
                    features = analyze_raw_payload(payload)
                    _, sample_created = DiscoverySample.objects.get_or_create(
                        queue_row=row,
                        defaults={
                            "case": case,
                            "payload_sha256": features["sha256"],
                            "payload_size_bytes": len(payload),
                            "features": features,
                        },
                    )
                    if sample_created:
                        created_samples += 1

                queue_refs = list(case.queue_references or [])
                known_ids = {
                    item.get("queue_id")
                    for item in queue_refs
                    if isinstance(item, dict)
                }
                for row in session_rows:
                    if row.pk not in known_ids:
                        queue_refs.append(
                            {
                                "queue_id": row.pk,
                                "session_id": str(session_id),
                                "transport": row.transport,
                                "received_at": row.received_at.isoformat(),
                            }
                        )
                case.queue_references = queue_refs
                case.raw_sample_count = DiscoverySample.objects.filter(case=case).count()
                case.save(update_fields=("queue_references", "raw_sample_count", "updated_at"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported queue rows: {created_samples}; new discovery cases: {created_cases}; "
                f"sessions scanned: {len(grouped)}"
            )
        )
