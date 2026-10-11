from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class NormalizedTelemetry:
    """Protocol-independent, normalized representation of one device report."""

    device_id: int
    device_time: datetime
    server_received_at: datetime
    latitude: Decimal | None
    longitude: Decimal | None
    gps_valid: bool
    accuracy: Decimal | None = None
    altitude_m: int | None = None
    satellites: int | None = None
    speed_kmh: Decimal | None = None
    heading_deg: int | None = None
    motion: bool | None = None
    ignition: bool | None = None
    battery_voltage: Decimal | None = None
    external_voltage: Decimal | None = None
    gsm_signal: int | None = None
    odometer: Decimal | None = None
    engine_hours: Decimal | None = None
    fuel_level: Decimal | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
