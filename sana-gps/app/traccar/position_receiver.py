from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from app.processing.telemetry import NormalizedTelemetry
from app.repositories.device import DeviceRepository
from app.repositories.gps_telemetry import GPSTelemetryRepository
from app.traccar.client import TraccarClient

logger = logging.getLogger(__name__)


def _datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return result if result.is_finite() else None


class TraccarPositionReceiver:
    """Validate Traccar's JSON position and persist through SANA's canonical repository."""

    def __init__(
        self,
        *,
        client: TraccarClient,
        device_repository: DeviceRepository,
        telemetry_repository: GPSTelemetryRepository,
    ) -> None:
        self._client = client
        self._devices = device_repository
        self._telemetry = telemetry_repository

    def receive_payload(self, payload: Any) -> dict[str, int]:
        positions = payload if isinstance(payload, list) else [payload]
        result = {"received": 0, "saved": 0, "unknown": 0, "invalid": 0}
        for position in positions:
            result["received"] += 1
            if not isinstance(position, dict):
                result["invalid"] += 1
                continue
            try:
                if self._receive_position(position):
                    result["saved"] += 1
                else:
                    result["unknown"] += 1
            except (ValueError, TypeError, KeyError):
                result["invalid"] += 1
                logger.warning("Rejected malformed Traccar position payload")
            except Exception:
                result["invalid"] += 1
                logger.exception("Could not persist Traccar position")
        return result

    def _receive_position(self, position: dict[str, Any]) -> bool:
        raw_device_id = position.get("deviceId")
        try:
            traccar_device_id = int(raw_device_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("missing Traccar deviceId") from exc

        traccar_device = self._client.get_device_by_id(traccar_device_id)
        if not traccar_device:
            logger.warning("Traccar position references unknown Traccar device id=%s", traccar_device_id)
            return False
        unique_id = str(traccar_device.get("uniqueId") or "").strip()
        device = self._devices.find_by_imei(unique_id)
        if device is None:
            # Unknown devices are staged by the API reconciliation worker. Do not
            # create a fleet_device or write telemetry until SANA admin approval.
            logger.info("Ignoring position from unapproved Traccar device uniqueId=%s", unique_id)
            return False

        device_time = (
            _datetime(position.get("fixTime"))
            or _datetime(position.get("deviceTime"))
            or _datetime(position.get("serverTime"))
        )
        if device_time is None:
            raise ValueError("Traccar position has no usable timestamp")
        received_at = datetime.now(timezone.utc)

        lat = _decimal(position.get("latitude"))
        lon = _decimal(position.get("longitude"))
        coords_present = lat is not None and lon is not None
        gps_valid = bool(position.get("valid", coords_present)) and coords_present
        if gps_valid and not (
            Decimal("-90") <= lat <= Decimal("90")
            and Decimal("-180") <= lon <= Decimal("180")
        ):
            gps_valid = False
        if not gps_valid:
            lat = lon = None

        # Traccar reports Position.speed in knots; SANA stores km/h.
        speed = _decimal(position.get("speed"))
        if speed is not None:
            speed = speed * Decimal("1.852")
        heading = _decimal(position.get("course"))
        if heading is not None:
            heading = heading % Decimal("360")
        altitude = _decimal(position.get("altitude"))
        accuracy = _decimal(position.get("accuracy"))
        attributes = position.get("attributes")
        if not isinstance(attributes, dict):
            attributes = {}
        attributes = {
            **attributes,
            "source": "traccar-json",
            "traccar_device_id": traccar_device_id,
            "traccar_protocol": position.get("protocol"),
            "time_source": (
                "fixTime" if position.get("fixTime") else
                "deviceTime" if position.get("deviceTime") else "serverTime"
            ),
        }
        record = NormalizedTelemetry(
            device_id=device.id,
            device_time=device_time,
            server_received_at=received_at,
            latitude=lat,
            longitude=lon,
            gps_valid=gps_valid,
            accuracy=accuracy,
            speed=speed,
            heading=heading,
            altitude=altitude,
            motion=(speed > 0 if speed is not None else None),
            satellites=None,
            attributes=attributes,
        )
        raw_payload = json.dumps(
            position, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        self._telemetry.save_batch(
            (record,), protocol="traccar-json", raw_payload=raw_payload
        )
        return True
