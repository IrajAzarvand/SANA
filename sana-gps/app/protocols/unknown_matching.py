from __future__ import annotations

from collections.abc import Iterable


_ASCII_DIGITS = b"0123456789"


def match_registered_identifiers(
    payload: bytes,
    identifiers: Iterable[str],
) -> tuple[str, ...]:
    """Find complete ASCII identifiers in a raw stream, avoiding partial digit matches.

    This conservative first pass intentionally does not guess binary/BCD encodings.
    Identifiers are returned in input order with duplicates removed.
    """
    if not payload:
        return ()

    matches: list[str] = []
    seen: set[str] = set()
    for raw_identifier in identifiers:
        identifier = raw_identifier.strip()
        if not identifier or identifier in seen:
            continue
        seen.add(identifier)
        encoded = identifier.encode("ascii", errors="ignore")
        if not encoded or len(encoded) != len(identifier):
            continue

        start = 0
        while True:
            index = payload.find(encoded, start)
            if index < 0:
                break
            end = index + len(encoded)
            left_is_digit = index > 0 and payload[index - 1] in _ASCII_DIGITS
            right_is_digit = end < len(payload) and payload[end] in _ASCII_DIGITS
            if not left_is_digit and not right_is_digit:
                matches.append(identifier)
                break
            start = index + 1

    return tuple(matches)
