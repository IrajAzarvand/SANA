from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from .sample_analysis import analyze_raw_payload


def _extract_jt808_header_evidence(payload: bytes) -> dict[str, Any]:
    """Extract conservative JT/T 808 framing/header evidence from 0x7E frames.

    This is evidence only: it does not validate checksum, decode the body, or
    assign a protocol to a device.
    """
    frames: list[dict[str, Any]] = []
    terminal_ids: list[str] = []
    start = 0
    while True:
        begin = payload.find(b"\x7e", start)
        if begin < 0:
            break
        end = payload.find(b"\x7e", begin + 1)
        if end < 0:
            break
        frame = payload[begin + 1:end]
        start = end
        # Base JT/T 808 header: msg id (2), attributes (2), terminal BCD (6),
        # serial number (2). Escaping can alter the body, so only inspect a
        # conservative raw-frame header prefix here.
        if len(frame) < 12:
            continue
        message_id = int.from_bytes(frame[0:2], "big")
        attributes = int.from_bytes(frame[2:4], "big")
        terminal_bcd = frame[4:10]
        nibbles = "".join(f"{byte >> 4:x}{byte & 0x0f:x}" for byte in terminal_bcd)
        if all(char in "0123456789" for char in nibbles):
            terminal_id = nibbles.lstrip("0") or "0"
            terminal_ids.append(terminal_id)
        frames.append({
            "message_id": f"0x{message_id:04X}",
            "attributes": attributes,
            "terminal_id_bcd_raw": terminal_bcd.hex(),
            "terminal_id_digits": nibbles,
            "frame_bytes": len(frame) + 2,
        })
        if len(frames) >= 50:
            break

    return {
        "jt808_frame_evidence_count": len(frames),
        "jt808_frame_evidence": frames[:10],
        "jt808_terminal_id_candidates": sorted(set(terminal_ids)),
    }


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
        protocol_evidence = _extract_jt808_header_evidence(combined)
        # Compare the header BCD field only as an exact identifier candidate.
        # Do not infer that an IMEI is equivalent to a protocol terminal number.
        header_ids = set(protocol_evidence["jt808_terminal_id_candidates"])
        exact_header_matches = sorted(header_ids.intersection(identifiers))
        candidates = sorted(set(candidates) | set(exact_header_matches))
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
                "protocol_evidence": protocol_evidence,
                "exact_header_identifier_matches": exact_header_matches,
                "protocol_hints": (
                    ["jt808_like_framing"]
                    if protocol_evidence["jt808_frame_evidence_count"]
                    else []
                ),
                "evidence_strings": features.get("printable_runs", []),
            }
        )

    return reports
