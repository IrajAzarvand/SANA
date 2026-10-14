from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.processing.telemetry import NormalizedTelemetry
from app.protocols.decoders.teltonika import TeltonikaAVLRecord


class TeltonikaNormalizer:
    """Map decoded Codec 8 records to SANA units without guessing IO meanings."""

    def normalize(
        self,
        *,
        device_id: int,
        record: TeltonikaAVLRecord,
        server_received_at: datetime,
    ) -> NormalizedTelemetry:
        latitude = self._coordinate(record.latitude, Decimal("-90"), Decimal("90"))
        longitude = self._coordinate(record.longitude, Decimal("-180"), Decimal("180"))
        satellites = self._bounded_int(record.satellites, 0, 255)
        gps_valid = (
            latitude is not None
            and longitude is not None
            and satellites is not None
            and satellites > 0
            and not (latitude == 0 and longitude == 0)
        )
        if not gps_valid:
            latitude = None
            longitude = None

        heading_value = self._decimal(record.heading_deg, minimum=Decimal("0"))
        heading = (
            heading_value
            if heading_value is not None and heading_value < Decimal("360")
            else None
        )
        speed = self._decimal(record.speed_kmh, minimum=Decimal("0"))
        altitude = self._decimal(record.altitude_m)
        if altitude is not None and not Decimal("-20000") <= altitude <= Decimal("100000"):
            altitude = None

        # IO IDs remain raw until an explicitly configured DeviceModel/profile
        # defines their meaning. In particular, do not guess ignition, motion,
        # fuel, voltage, or odometer from vendor-specific IDs.
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
            speed=speed,
            heading=heading,
            altitude=altitude,
            satellites=satellites,
            # These remain NULL until a device-model profile maps them.
            accuracy=None,
            motion=None,
            ignition=None,
            battery_voltage=None,
            external_voltage=None,
            gsm_signal=None,
            odometer=None,
            engine_hours=None,
            fuel_level=None,
            attributes=attributes,
        )

    @staticmethod
    def _coordinate(
        value: int | float | Decimal | None,
        minimum: Decimal,
        maximum: Decimal,
    ) -> Decimal | None:
        if value is None:
            return None
        try:
            number = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return None
        if not number.is_finite() or not minimum <= number <= maximum:
            return None
        return number.quantize(Decimal("0.0000001"))

    @staticmethod
    def _decimal(
        value: int | float | Decimal | None,
        *,
        minimum: Decimal | None = None,
    ) -> Decimal | None:
        if value is None:
            return None
        try:
            number = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return None
        if not number.is_finite() or (minimum is not None and number < minimum):
            return None
        return number.quantize(Decimal("0.01"))

    @staticmethod
    def _bounded_int(value: int, minimum: int, maximum: int) -> int | None:
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        return value if minimum <= value <= maximum else None
