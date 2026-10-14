from __future__ import annotations

from app.database.pool import DatabaseConnectionPool
from app.processing.telemetry import NormalizedTelemetry
from app.repositories.gps_telemetry import GPSTelemetryRepository
from app.protocols.decoders.gt06 import GT06Position
from datetime import datetime, timezone
from decimal import Decimal


class GT06PositionRepository:
    """Compatibility adapter that persists GT06 reports to canonical GPS tables."""

    def __init__(self, pool: DatabaseConnectionPool) -> None:
        self._telemetry = GPSTelemetryRepository(pool)

    def save(self, *, device_id: int, position: GT06Position, raw_frame: bytes) -> None:
        received_at = datetime.now(timezone.utc)
        latitude = Decimal(str(position.latitude)).quantize(Decimal("0.0000001"))
        longitude = Decimal(str(position.longitude)).quantize(Decimal("0.0000001"))
        valid = (
            Decimal("-90") <= latitude <= Decimal("90")
            and Decimal("-180") <= longitude <= Decimal("180")
            and not (latitude == 0 and longitude == 0)
        )
        record = NormalizedTelemetry(
            device_id=device_id,
            device_time=position.gps_time,
            server_received_at=received_at,
            latitude=latitude if valid else None,
            longitude=longitude if valid else None,
            gps_valid=valid,
            speed=Decimal(str(position.speed_kmh)).quantize(Decimal("0.01")),
            heading=Decimal(str(position.course)).quantize(Decimal("0.01"))
                if 0 <= position.course < 360 else None,
            satellites=position.satellites if 0 <= position.satellites <= 255 else None,
            attributes={"gt06": {"source": "GT06"}},
        )
        self._telemetry.save_batch(
            (record,),
            protocol="gt06",
            raw_payload=raw_frame,
        )
