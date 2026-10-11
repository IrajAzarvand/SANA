from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.protocols.h02_binary import decode_h02_binary


SAMPLE = bytes.fromhex(
    "2491765157200447151110263751278764045559260c000000fffffbff"
    "000000000000000001b00b0d544ff408"
)


def test_decodes_observed_45_byte_h02_report():
    report = decode_h02_binary(SAMPLE)

    assert report.imei == "9176515720"
    assert report.gps_time == datetime(2026, 10, 11, 4, 47, 15, tzinfo=timezone.utc)
    assert report.latitude == pytest.approx(37 + 51.2787 / 60)
    # H02 packs longitude across a BCD nibble boundary.
    assert report.longitude == pytest.approx(45 + 59.26 / 60)
    assert report.speed_kmh == 0
    assert report.valid is False
    assert report.battery_level == 100
    assert report.raw == SAMPLE


def test_rejects_wrong_frame_length():
    with pytest.raises(ValueError, match="expected 45-byte"):
        decode_h02_binary(SAMPLE[:-1])
