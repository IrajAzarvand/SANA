from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.processing.telemetry import NormalizedTelemetry
from app.protocols.teltonika.decoder import TeltonikaAVLRecord


class TeltonikaNormalizer:
    """Normalize Codec 8 fields without guessing device-specific IO meanings."""

    def normalize(
        self,
        *,
        device_id: int,
        record: TeltonikaAVLRecord,
        server_received_at: datetime,
    ) -> NormalizedTelemetry:
        latitude = self._coordinate(record.latitude, -90, 90)
        longitude = self._coordinate(record.longitude, -180, 180)
        gps_valid = (
            latitude is not None
            and longitude is not None
            and record.satellites > 0
            and not (latitude == 0 and longitude == 0)
        )
        if not gps_valid:
            latitude = None
            longitude = None

        heading = record.heading_deg if 0 <= record.heading_deg <= 360 else None
        speed = self._decimal(record.speed_kmh, minimum=0)
        altitude = record.altitude_m if -20_000 <= record.altitude_m <= 100_000 else None
        satellites = record.satellites if 0 <= record.satellites <= 255 else None

        # IO IDs are preserved verbatim until a configured profile maps them to
        # standard SANA fields. We deliberately do not infer ignition/fuel IDs.
        attributes = {
            "teltonika": {
                "codec": 8,
                "priority": record.priority,
                "event_io_id": record.event_io_id,
                "io": {str(io_id): value for io_id, value in record.io_elements.items()},
            }
        }

        return NormalizedTelemetry(
            device_id=device_id,
            device_time=record.device_time,
            server_received_at=server_received_at,
            latitude=latitude,
            longitude=longitude,
            gps_valid=gps_valid,
            speed_kmh=speed,
            heading_deg=heading,
            altitude_m=altitude,
            satellites=satellites,
            attributes=attributes,
        )

    @staticmethod
    def _coordinate(value: float, minimum: int, maximum: int) -> Decimal | None:
        try:
            coordinate = Decimal(str(value)).quantize(Decimal("0.0000001"))
        except (InvalidOperation, ValueError):
            return None
        if not coordinate.is_finite() or not Decimal(minimum) <= coordinate <= Decimal(maximum):
            return None
        return coordinate

    @staticmethod
    def _decimal(value: int | float | Decimal | None, *, minimum: int) -> Decimal | None:
        if value is None:
            return None
        try:
            number = Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None
        if not number.is_finite() or number < Decimal(minimum):
            return None
        return number.quantize(Decimal("0.01"))
