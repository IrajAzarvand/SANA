from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from typing import Any


_PRINTABLE_RUN = re.compile(rb"[ -~]{4,80}")


def analyze_raw_payload(payload: bytes) -> dict[str, Any]:
    """Extract protocol-neutral evidence without guessing a protocol."""
    data = bytes(payload)
    if not data:
        return {
            "byte_length": 0,
            "sha256": hashlib.sha256(data).hexdigest(),
            "entropy_bits_per_byte": 0.0,
            "printable_ascii_ratio": 0.0,
            "prefix_hex": "",
            "suffix_hex": "",
            "printable_runs": [],
            "distinct_byte_values": 0,
            "zero_byte_count": 0,
        }

    counts = Counter(data)
    length = len(data)
    entropy = -sum(
        (count / length) * math.log2(count / length)
        for count in counts.values()
    )
    printable_count = sum(32 <= value <= 126 for value in data)
    runs = []
    seen_runs: set[str] = set()
    for match in _PRINTABLE_RUN.finditer(data):
        value = match.group().decode("ascii", errors="strict")
        if value not in seen_runs:
            runs.append(value)
            seen_runs.add(value)
        if len(runs) >= 20:
            break

    return {
        "byte_length": length,
        "sha256": hashlib.sha256(data).hexdigest(),
        "entropy_bits_per_byte": round(entropy, 4),
        "printable_ascii_ratio": round(printable_count / length, 4),
        "prefix_hex": data[:32].hex(),
        "suffix_hex": data[-16:].hex(),
        "printable_runs": runs,
        "distinct_byte_values": len(counts),
        "zero_byte_count": counts.get(0, 0),
    }
