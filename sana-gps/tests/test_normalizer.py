from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.processing.telemetry import NormalizedTelemetry
from app.protocols.teltonika.decoder import TeltonikaAVLRecord
from app.protocols.teltonika.normalizer import TeltonikaNormalizer


NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)


def _record(
    *,
    latitude: float = 35.7,
    longitude: float = 51.4,
    satellites: int = 8,
    heading: int = 90,
    io: dict[int, int] | None = None,
) -> TeltonikaAVLRecord:
    return TeltonikaAVLRecord(
        device_time=NOW,
        priority=1,
        longitude=longitude,
        latitude=latitude,
        altitude_m=123,
        heading_deg=heading,
        satellites=satellites,
        speed_kmh=50,
        event_io_id=239,
        io_elements=io or {},
    )


def test_normalizer_emits_canonical_decimal_fields_and_preserves_unknown_io() -> None:
    result = TeltonikaNormalizer().normalize(
        device_id=7,
        record=_record(latitude=35.7123456, longitude=51.4234567, io={239: 1}),
        server_received_at=NOW,
    )

    assert result.gps_valid is True
    assert result.latitude == Decimal("35.7123456")
    assert result.longitude == Decimal("51.4234567")
    assert result.speed == Decimal("50.00")
    assert result.heading == Decimal("90.00")
    assert result.altitude == Decimal("123.00")
    assert result.motion is None
    assert result.ignition is None
    assert result.fuel_level is None
    assert result.attributes["teltonika"]["io"] == {"239": 1}


@pytest.mark.parametrize("heading", [-1, 360, 400])
def test_normalizer_rejects_heading_outside_half_open_range(heading: int) -> None:
    result = TeltonikaNormalizer().normalize(
        device_id=7, record=_record(heading=heading), server_received_at=NOW
    )
    assert result.heading is None


def test_normalizer_turns_no_fix_into_null_current_coordinates() -> None:
    result = TeltonikaNormalizer().normalize(
        device_id=7, record=_record(latitude=0, longitude=0), server_received_at=NOW
    )
    assert result.gps_valid is False
    assert result.latitude is None
    assert result.longitude is None


def test_normalized_telemetry_rejects_naive_timestamps() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        NormalizedTelemetry(
            device_id=1,
            device_time=datetime(2026, 1, 1),
            server_received_at=NOW,
        )


def test_normalized_telemetry_rejects_invalid_gps_coordinate_contract() -> None:
    with pytest.raises(ValueError, match="invalid GPS fix"):
        NormalizedTelemetry(
            device_id=1,
            device_time=NOW,
            server_received_at=NOW,
            latitude=Decimal("1"),
            longitude=Decimal("2"),
            gps_valid=False,
        )
