from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class NormalizedTelemetry:
    """Protocol-independent telemetry using SANA's canonical field names.

    The decoder must produce protocol fields only. Unit conversion and field
    mapping belong in a protocol-specific normalizer. Unknown measurements stay
    None; they are never guessed from vendor IO identifiers.
    """

    device_id: int
    device_time: datetime
    server_received_at: datetime
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    gps_valid: bool = False
    accuracy: Decimal | None = None
    speed: Decimal | None = None
    heading: Decimal | None = None
    altitude: Decimal | None = None
    motion: bool | None = None
    ignition: bool | None = None
    satellites: int | None = None
    battery_voltage: Decimal | None = None
    external_voltage: Decimal | None = None
    gsm_signal: int | None = None
    odometer: Decimal | None = None
    engine_hours: Decimal | None = None
    fuel_level: Decimal | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.device_id <= 0:
            raise ValueError("device_id must be a positive integer")
        for name, value in (
            ("device_time", self.device_time),
            ("server_received_at", self.server_received_at),
        ):
            if not isinstance(value, datetime) or value.tzinfo is None:
                raise ValueError(f"{name} must be a timezone-aware datetime")
        if self.gps_valid:
            if self.latitude is None or self.longitude is None:
                raise ValueError("valid GPS fix requires latitude and longitude")
            if not (Decimal("-90") <= self.latitude <= Decimal("90")):
                raise ValueError("latitude is outside [-90, 90]")
            if not (Decimal("-180") <= self.longitude <= Decimal("180")):
                raise ValueError("longitude is outside [-180, 180]")
        elif self.latitude is not None or self.longitude is not None:
            raise ValueError("invalid GPS fix must not expose current coordinates")
        if self.heading is not None and not (Decimal("0") <= self.heading < Decimal("360")):
            raise ValueError("heading must be in [0, 360)")
        if self.speed is not None and self.speed < 0:
            raise ValueError("speed must not be negative")
        if self.motion not in (True, False, None):
            raise ValueError("motion must be bool or None")

    # Transitional aliases keep the existing transport handlers compatible
    # while all new code uses the canonical names from telemetry.md.
    @property
    def speed_kmh(self) -> Decimal | None:
        return self.speed

    @property
    def heading_deg(self) -> Decimal | None:
        return self.heading

    @property
    def altitude_m(self) -> Decimal | None:
        return self.altitude
