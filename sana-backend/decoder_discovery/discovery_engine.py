from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from .sample_analysis import analyze_raw_payload


def find_identifier_candidates(
    payload: bytes,
    registered_identifiers: Iterable[str],
    *,
    explicit_candidate: str = "",
) -> list[str]:
    """Find identifier evidence without assigning a protocol.

    ASCII matches are boundary-aware for numeric identifiers. Binary/BCD decoding
    is intentionally not guessed here; a candidate must be visible as ASCII or
    already have been recorded by the existing queue matcher.
    """
    data = bytes(payload)
    candidates: set[str] = set()

    if explicit_candidate:
        candidates.add(str(explicit_candidate).strip())

    for raw_identifier in registered_identifiers:
        identifier = str(raw_identifier).strip()
        if not identifier:
            continue
        needle = identifier.encode("ascii", errors="ignore")
        if not needle or needle not in data:
            continue

        # Avoid treating a short digit sequence inside a longer numeric field
        # as a confident match. Non-numeric identifiers use a direct byte match.
        if identifier.isdigit():
            start = 0
            while True:
                index = data.find(needle, start)
                if index < 0:
                    break
                before = data[index - 1] if index else None
                after_index = index + len(needle)
                after = data[after_index] if after_index < len(data) else None
                if not (before is not None and 48 <= before <= 57) and not (
                    after is not None and 48 <= after <= 57
                ):
                    candidates.add(identifier)
                    break
                start = index + 1
        else:
            candidates.add(identifier)

    return sorted(candidates)


def analyze_unknown_sessions(
    rows: Iterable[Any],
    registered_identifiers: Iterable[str],
    *,
    max_session_bytes: int = 8192,
) -> list[dict[str, Any]]:
    """Analyze existing UnknownGPSData rows in memory; never copies or mutates them."""
    identifiers = tuple(str(value).strip() for value in registered_identifiers if str(value).strip())
    grouped: dict[str, list[Any]] = defaultdict(list)
    for row in rows:
        grouped[str(row.session_id)].append(row)

    reports: list[dict[str, Any]] = []
    for session_id, session_rows in grouped.items():
        ordered = sorted(session_rows, key=lambda row: row.id)
        payload = bytearray()
        truncated = False
        for row in ordered:
            chunk = bytes(row.raw_payload)
            if len(payload) + len(chunk) > max_session_bytes:
                truncated = True
                break
            payload.extend(chunk)

        combined = bytes(payload)
        recorded_candidates = {
            str(row.identifier_candidate).strip()
            for row in ordered
            if getattr(row, "identifier_candidate", "")
        }
        candidates = find_identifier_candidates(
            combined,
            identifiers,
            explicit_candidate="",
        )
        candidates = sorted(set(candidates) | recorded_candidates)
        features = analyze_raw_payload(combined)
        reports.append(
            {
                "session_id": session_id,
                "row_ids": [row.id for row in ordered],
                "row_count": len(ordered),
                "transports": sorted({str(row.transport) for row in ordered}),
                "received_at_first": ordered[0].received_at.isoformat() if ordered[0].received_at else None,
                "received_at_last": ordered[-1].received_at.isoformat() if ordered[-1].received_at else None,
                "registered_identifier_candidates": candidates,
                "identifier_match_count": len(candidates),
                "identifier_match_status": (
                    "unique" if len(candidates) == 1 else
                    "ambiguous" if len(candidates) > 1 else
                    "unmatched"
                ),
                "truncated": truncated,
                "features": features,
                "evidence_strings": features.get("printable_runs", []),
            }
        )

    return reports
