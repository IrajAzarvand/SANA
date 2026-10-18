from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Max

from fleet.models import Device, UnknownGPSData

from decoder_discovery.discovery_engine import analyze_unknown_sessions
from decoder_discovery.internet_research import build_research_queries, search_protocol_references


class Command(BaseCommand):
    help = (
        "Read complete sessions from the existing unknown-GPS queue, search public "
        "web references for packet clues, and print findings without changing data."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=20,
            help="Maximum number of recent sessions to inspect (1..1000). All rows in each selected session are read.",
        )
        parser.add_argument(
            "--status",
            choices=("pending", "matched", "failed", "all"),
            default="all",
            help="Select sessions that contain at least one row with this status.",
        )
        parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    def handle(self, *args, **options):
        limit = options["limit"]
        if not 1 <= limit <= 1000:
            raise CommandError("--limit must be between 1 and 1000")

        session_query = UnknownGPSData.objects.all()
        if options["status"] != "all":
            session_query = session_query.filter(status=options["status"])

        selected_sessions = list(
            session_query.values("session_id")
            .annotate(last_seen=Max("received_at"))
            .order_by("-last_seen")
            .values_list("session_id", flat=True)[:limit]
        )
        if not selected_sessions:
            self.stdout.write("No unknown-GPS sessions matched the requested status.")
            return

        # Select sessions first, then load every row in each session. The session is
        # never silently cut off at the row limit or at a byte limit.
        rows = list(
            UnknownGPSData.objects.filter(session_id__in=selected_sessions)
            .only(
                "id", "session_id", "transport", "raw_payload",
                "identifier_candidate", "received_at", "status",
            )
            .order_by("session_id", "id")
        )
        identifiers = tuple(
            Device.objects.order_by().values_list("imei", flat=True)
        )
        reports = analyze_unknown_sessions(
            rows,
            identifiers,
            max_session_bytes=0,
        )

        query_to_sessions: dict[str, list[str]] = {}
        for report in reports:
            report_queries = build_research_queries(report)
            report["internet_search_queries"] = report_queries
            for query in report_queries:
                query_to_sessions.setdefault(query, []).append(report["session_id"])

        # Search the unique clues only once; repeated sessions with the same packet
        # signature reuse the same public search results. No raw packet is uploaded.
        unique_queries = list(query_to_sessions)[:12]
        search_report = search_protocol_references(unique_queries)
        results_by_query: dict[str, list[dict]] = {query: [] for query in unique_queries}
        for result in search_report["results"]:
            results_by_query.setdefault(result["matched_query"], []).append(result)

        for report in reports:
            report["internet_search_results"] = [
                result
                for query in report["internet_search_queries"]
                for result in results_by_query.get(query, [])
            ]
            report["internet_search_errors"] = [
                error for error in search_report["errors"]
                if error["query"] in report["internet_search_queries"]
            ]

        result = {
            "source_tables": ["fleet_device", "fleet_unknowngpsdata"],
            "registered_device_count": len(identifiers),
            "sessions_requested": limit,
            "sessions_analyzed": len(reports),
            "raw_rows_read": len(rows),
            "complete_session_payloads": all(not report["truncated"] for report in reports),
            "unique_internet_queries": len(unique_queries),
            "internet_results": len(search_report["results"]),
            "internet_search_errors": search_report["errors"],
            "raw_payload_uploaded_to_search_providers": False,
            "database_writes": 0,
            "database_deletes": 0,
            "protocol_assigned": False,
            "sessions": reports,
        }
        if options["json"]:
            self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
            return

        self.stdout.write(
            "Real-data protocol research (read-only): "
            f"devices={result['registered_device_count']} "
            f"sessions={result['sessions_analyzed']} "
            f"raw_rows={result['raw_rows_read']} "
            f"unique_web_queries={result['unique_internet_queries']} "
            f"web_results={result['internet_results']}"
        )
        self.stdout.write(
            "Complete sessions loaded. No raw packet was uploaded to search providers. "
            "No database records were created, updated, or deleted."
        )

        for report in reports:
            features = report["features"]
            message_ids = sorted({
                item["message_id"]
                for item in report["protocol_evidence"]["jt808_frame_evidence"]
            })
            self.stdout.write("")
            self.stdout.write(
                f"SESSION {report['session_id']} | rows={report['row_count']} "
                f"| transports={','.join(report['transports'])} "
                f"| bytes={features['byte_length']} "
                f"| sha256={features['sha256']} "
                f"| identifier_status={report['identifier_match_status']} "
                f"| identity_confirmed={str(report['identity_confirmed']).lower()}"
            )
            self.stdout.write(
                f"  Evidence: hints={','.join(report['protocol_hints']) or '-'} "
                f"message_ids={','.join(message_ids) or '-'} "
                f"terminal_ids={','.join(report['protocol_evidence']['jt808_terminal_id_candidates']) or '-'}"
            )
            self.stdout.write(
                f"  Payload signature: prefix_hex={features['prefix_hex']} "
                f"suffix_hex={features['suffix_hex']} "
                f"entropy={features['entropy_bits_per_byte']}"
            )
            self.stdout.write(
                f"  Search queries: {'; '.join(report['internet_search_queries'])}"
            )
            if not report["internet_search_results"]:
                self.stdout.write("  Internet results: no results returned.")
            else:
                self.stdout.write("  Internet findings:")
                for item in report["internet_search_results"]:
                    metadata = []
                    if item.get("language"):
                        metadata.append(f"language={item['language']}")
                    if item.get("license"):
                        metadata.append(f"license={item['license']}")
                    if item.get("stars") is not None:
                        metadata.append(f"stars={item['stars']}")
                    suffix = f" ({', '.join(metadata)})" if metadata else ""
                    self.stdout.write(
                        f"    - [{item['provider']}] {item['title']}{suffix}\n"
                        f"      {item['url']}\n"
                        f"      {item.get('snippet', '')}"
                    )
            if report["internet_search_errors"]:
                self.stdout.write("  Search errors:")
                for error in report["internet_search_errors"]:
                    self.stdout.write(
                        f"    - {error['provider']} for {error['query']}: {error['error']}"
                    )
