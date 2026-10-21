from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.processing.telemetry import NormalizedTelemetry
from app.repositories.gps_telemetry import GPSTelemetryRepository


def record() -> NormalizedTelemetry:
    now = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
    return NormalizedTelemetry(
        device_id=9,
        device_time=now,
        server_received_at=now,
        latitude=Decimal("35.7000000"),
        longitude=Decimal("51.4000000"),
        gps_valid=True,
    )


@pytest.mark.parametrize("method", ["save", "save_batch"])
def test_legacy_repository_refuses_to_store_raw_telemetry(method):
    pool = MagicMock()
    repository = GPSTelemetryRepository(pool)

    with pytest.raises(RuntimeError, match="SANA no longer stores raw GPS telemetry"):
        if method == "save":
            repository.save(
                device_id=9,
                protocol="teltonika",
                gps_time=record().device_time,
                latitude=35.7,
                longitude=51.4,
                raw_payload=b"raw packet",
            )
        else:
            repository.save_batch((record(),), protocol="teltonika", raw_payload=b"raw packet")

    pool.connection.assert_not_called()
