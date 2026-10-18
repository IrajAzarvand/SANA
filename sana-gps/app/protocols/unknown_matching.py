from __future__ import annotations

from collections.abc import Iterable


_ASCII_DIGITS = b"0123456789"


def _identifier_encodings(identifier: str) -> tuple[bytes, ...]:
    """Return conservative byte representations of a decimal device identifier.

    Includes literal ASCII, packed BCD (including common odd-digit padding), and
    minimal-width unsigned integer bytes in both byte orders. These are matching
    hypotheses only; a match never identifies or assigns a protocol.
    """
    encodings: list[bytes] = []
    try:
        ascii_value = identifier.encode("ascii")
    except UnicodeEncodeError:
        return ()
    encodings.append(ascii_value)

    if not identifier.isdigit():
        return tuple(encodings)

    # Packed BCD: two decimal digits per byte.
    digits = identifier
    if len(digits) % 2:
        encodings.append(bytes.fromhex("0" + "".join(
            digits[index:index + 1] for index in range(len(digits))
        )))
        encodings.append(bytes.fromhex("".join(
            digits[index:index + 2] for index in range(0, len(digits) - 1, 2)
        ) + digits[-1] + "f"))
    else:
        encodings.append(bytes.fromhex("".join(
            digits[index:index + 2] for index in range(0, len(digits), 2)
        )))

    # Some devices transmit the identifier as a binary integer, not decimal text.
    number = int(identifier)
    width = max(1, (number.bit_length() + 7) // 8)
    big_endian = number.to_bytes(width, byteorder="big", signed=False)
    encodings.extend((big_endian, big_endian[::-1]))

    # Keep only unique, non-empty representations.
    return tuple(dict.fromkeys(value for value in encodings if value))


def match_registered_identifiers(
    payload: bytes,
    identifiers: Iterable[str],
) -> tuple[str, ...]:
    """Find registered IDs in ASCII, packed-BCD, or integer-byte form.

    This produces candidates, not protocol conclusions. Ambiguous streams should
    remain pending; a match must never set the device's protocol.
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

        for encoded in _identifier_encodings(identifier):
            start = 0
            while True:
                index = payload.find(encoded, start)
                if index < 0:
                    break
                end = index + len(encoded)
                # Digit boundaries are meaningful only for a literal ASCII match.
                if encoded != identifier.encode("ascii", errors="ignore"):
                    matches.append(identifier)
                    break
                left_is_digit = index > 0 and payload[index - 1] in _ASCII_DIGITS
                right_is_digit = end < len(payload) and payload[end] in _ASCII_DIGITS
                if not left_is_digit and not right_is_digit:
                    matches.append(identifier)
                    break
                start = index + 1
            if identifier in matches:
                break

    return tuple(matches)
