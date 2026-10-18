from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from fleet.models import Device, UnknownGPSData

from decoder_discovery.discovery_engine import analyze_unknown_sessions


class Command(BaseCommand):
    help = (
        "Analyze existing unknown GPS queue rows directly, without copying payloads "
        "or changing any database records."
    )

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=500, help="Maximum raw rows to inspect (1..10000).")
        parser.add_argument("--max-session-bytes", type=int, default=8192)
        parser.add_argument("--status", choices=("pending", "matched", "failed", "all"), default="all")
        parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    def handle(self, *args, **options):
        limit = options["limit"]
        max_session_bytes = options["max_session_bytes"]
        if not 1 <= limit <= 10000:
            raise CommandError("--limit must be between 1 and 10000")
        if not 1 <= max_session_bytes <= 1_048_576:
            raise CommandError("--max-session-bytes must be between 1 and 1048576")

        rows_query = UnknownGPSData.objects.all().order_by("id")
        if options["status"] != "all":
            rows_query = rows_query.filter(status=options["status"])
        rows = list(
            rows_query.only(
                "id", "session_id", "transport", "raw_payload",
                "identifier_candidate", "received_at",
            )[:limit]
        )
        identifiers = tuple(
            Device.objects.order_by().values_list("imei", flat=True)
        )
        reports = analyze_unknown_sessions(
            rows,
            identifiers,
            max_session_bytes=max_session_bytes,
        )

        result = {
            "source_tables": ["fleet_device", "fleet_unknowngpsdata"],
            "registered_device_count": len(identifiers),
            "raw_rows_read": len(rows),
            "sessions_analyzed": len(reports),
            "database_writes": 0,
            "database_deletes": 0,
            "protocol_assigned": False,
            "sessions": reports,
        }
        if options["json"]:
            self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
            return

        self.stdout.write(
            "Read-only discovery scan: "
            f"devices={result['registered_device_count']} "
            f"raw_rows={result['raw_rows_read']} "
            f"sessions={result['sessions_analyzed']}"
        )
        self.stdout.write("No database records were created, updated, or deleted.")
        for report in reports:
            features = report["features"]
            self.stdout.write(
                f"session={report['session_id']} rows={report['row_count']} "
                f"identifier_status={report['identifier_match_status']} "
                f"identifiers={','.join(report['registered_identifier_candidates']) or '-'} "
                f"bytes={features['byte_length']} entropy={features['entropy_bits_per_byte']} "
                f"printable={','.join(report['evidence_strings']) or '-'}"
            )
