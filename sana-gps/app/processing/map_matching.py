from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.database.pool import DatabaseConnectionPool
from app.traccar.client import TraccarClient

_LOGGER = logging.getLogger(__name__)
_ENDPOINT = "https://api.neshan.org/v3/map-matching"
_MAX_POINTS_PER_REQUEST = 100
_RECENT_WINDOW_MINUTES = 3
_DEFAULT_POLL_SECONDS = 10.0
_HTTP_TIMEOUT_SECONDS = 12.0


def _valid_coordinate(latitude: object, longitude: object) -> tuple[float, float] | None:
    try:
        lat, lon = float(latitude), float(longitude)
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon


def _request_matched_points(
    api_key: str,
    points: list[tuple[int, float, float]],
) -> dict[int, tuple[float, float]]:
    """Return Neshan snapped coordinates keyed by index in the supplied route."""
    if len(points) < 2:
        return {}
    payload = {"path": "|".join(f"{lat:.7f},{lon:.7f}" for _, lat, lon in points)}
    request = Request(
        _ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Api-Key": api_key, "Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=_HTTP_TIMEOUT_SECONDS) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read(500).decode("utf-8", errors="replace")
        raise RuntimeError(f"Neshan map matching returned HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Neshan map matching request failed: {exc.__class__.__name__}") from exc

    matched: dict[int, tuple[float, float]] = {}
    for item in result.get("snappedPoints", []):
        try:
            index, location = int(item["originalIndex"]), item["location"]
        except (KeyError, TypeError, ValueError):
            continue
        if not 0 <= index < len(points):
            continue
        if isinstance(location, dict):
            coordinate = _valid_coordinate(location.get("latitude"), location.get("longitude"))
        elif isinstance(location, (list, tuple)) and len(location) >= 2:
            coordinate = _valid_coordinate(location[0], location[1])
        else:
            coordinate = None
        if coordinate is not None:
            matched[index] = coordinate
    return matched


def has_active_map_matching_viewers(pool: DatabaseConnectionPool) -> bool:
    """Neshan matching is enabled only while a map viewer heartbeat is current."""
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT EXISTS (SELECT 1 FROM gps.map_matching_watchers WHERE expires_at > CURRENT_TIMESTAMP)"
        ).fetchone()
    return bool(row and row[0])


def _parse_position_time(position: dict) -> datetime | None:
    for key in ("fixTime", "deviceTime", "serverTime"):
        value = position.get(key)
        if not isinstance(value, str) or not value:
            continue
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def process_pending_map_matches(
    pool: DatabaseConnectionPool,
    api_key: str,
    traccar_client: TraccarClient,
) -> int:
    """Fetch raw points from Traccar and persist only Neshan's snapped coordinates."""
    with pool.connection() as connection:
        devices = connection.execute(
            "SELECT id, imei FROM public.fleet_device WHERE imei IS NOT NULL AND btrim(imei) <> ''"
        ).fetchall()
    if not devices:
        return 0

    traccar_devices = traccar_client.list_devices()
    by_unique_id = {
        str(item.get("uniqueId") or "").strip(): int(item["id"])
        for item in traccar_devices
        if item.get("id") is not None and str(item.get("uniqueId") or "").strip()
    }
    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=_RECENT_WINDOW_MINUTES)
    saved = 0

    for sana_device_id, imei in devices:
        traccar_device_id = by_unique_id.get(str(imei).strip())
        if traccar_device_id is None:
            continue
        try:
            positions = traccar_client.list_positions(
                traccar_device_id,
                start.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                now.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            )
        except Exception:
            _LOGGER.exception("Could not fetch recent Traccar positions for device_id=%s", sana_device_id)
            continue

        valid = []
        for position in positions:
            try:
                position_id = int(position["id"])
            except (KeyError, TypeError, ValueError):
                continue
            if position.get("valid") is False:
                continue
            coordinate = _valid_coordinate(position.get("latitude"), position.get("longitude"))
            device_time = _parse_position_time(position)
            if coordinate is None or device_time is None:
                continue
            valid.append((position_id, device_time, coordinate[0], coordinate[1]))
        valid.sort(key=lambda point: (point[1], point[0]))
        valid = valid[-_MAX_POINTS_PER_REQUEST:]
        if len(valid) < 2:
            continue

        position_ids = [point[0] for point in valid]
        with pool.connection() as connection:
            rows = connection.execute(
                "SELECT traccar_position_id FROM gps.map_matched_position WHERE traccar_position_id = ANY(%s)",
                (position_ids,),
            ).fetchall()
        matched_ids = {int(row[0]) for row in rows}
        if all(point[0] in matched_ids for point in valid):
            continue

        request_points = [(point[0], point[2], point[3]) for point in valid]
        try:
            matches = _request_matched_points(api_key, request_points)
        except Exception:
            _LOGGER.exception("Neshan map matching failed for SANA device_id=%s", sana_device_id)
            continue
        if not matches:
            continue

        with pool.connection() as connection:
            with connection.transaction():
                for index, (latitude, longitude) in matches.items():
                    position_id, device_time, _, _ = valid[index]
                    if position_id in matched_ids:
                        continue
                    connection.execute(
                        """
                        INSERT INTO gps.map_matched_position
                            (traccar_position_id, traccar_device_id, device_id, device_time,
                             matched_latitude, matched_longitude, matched_geom, match_provider, matched_at)
                        VALUES (%s, %s, %s, %s, %s, %s,
                                ST_SetSRID(ST_MakePoint(%s::double precision, %s::double precision), 4326),
                                'neshan', CURRENT_TIMESTAMP)
                        ON CONFLICT (traccar_position_id) DO NOTHING
                        """,
                        (position_id, traccar_device_id, sana_device_id, device_time,
                         latitude, longitude, longitude, latitude),
                    )
                    saved += 1

    if saved:
        _LOGGER.info("Saved %d Traccar-linked Neshan map match(es)", saved)
    return saved


async def run_map_matching_worker(
    shutdown_event: asyncio.Event,
    pool: DatabaseConnectionPool,
    api_key: str | None,
    traccar_client: TraccarClient | None,
    poll_seconds: float = _DEFAULT_POLL_SECONDS,
) -> None:
    """Poll Traccar only while a map is open; never persist Traccar's raw telemetry."""
    if not api_key:
        _LOGGER.info("Neshan map matching disabled: NESHAN_MAP_MATCHING_API_KEY is not set")
        return
    if traccar_client is None:
        _LOGGER.warning("Neshan map matching disabled: Traccar API credentials are not configured")
        return

    while not shutdown_event.is_set():
        started = time.monotonic()
        work_task = None
        try:
            active = await asyncio.to_thread(has_active_map_matching_viewers, pool)
            if not active:
                _LOGGER.debug("Skipping Traccar/Neshan polling: no active map viewers")
            else:
                work_task = asyncio.create_task(
                    asyncio.to_thread(process_pending_map_matches, pool, api_key, traccar_client),
                    name="sana-neshan-map-matching-scan",
                )
                await asyncio.shield(work_task)
        except asyncio.CancelledError:
            try:
                if work_task is not None:
                    await work_task
            finally:
                raise
        except Exception:
            _LOGGER.exception("Traccar map-matching scan failed")
        delay = max(0.0, poll_seconds - (time.monotonic() - started))
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=delay)
        except asyncio.TimeoutError:
            pass
