from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.database.pool import DatabaseConnectionPool

_LOGGER = logging.getLogger(__name__)
_ENDPOINT = "https://api.neshan.org/v3/map-matching"
_MAX_POINTS_PER_REQUEST = 100
_RECENT_WINDOW_MINUTES = 3
_DEFAULT_POLL_SECONDS = 10.0
_HTTP_TIMEOUT_SECONDS = 12.0


def _valid_coordinate(latitude: object, longitude: object) -> tuple[float, float] | None:
    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon


def _request_matched_points(
    api_key: str,
    points: list[tuple[int, float, float]],
) -> dict[int, tuple[float, float]]:
    """Ask Neshan to snap one ordered route segment to the road network."""
    if len(points) < 2:
        return {}

    payload = {
        "path": "|".join(f"{latitude:.7f},{longitude:.7f}" for _, latitude, longitude in points)
    }
    request = Request(
        _ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Api-Key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=_HTTP_TIMEOUT_SECONDS) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        # Do not log the request headers or API key.
        detail = exc.read(500).decode("utf-8", errors="replace")
        raise RuntimeError(f"Neshan map matching returned HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Neshan map matching request failed: {exc}") from exc

    snapped = result.get("snappedPoints", [])
    matched: dict[int, tuple[float, float]] = {}
    for item in snapped:
        try:
            index = int(item["originalIndex"])
            location = item["location"]
        except (KeyError, TypeError, ValueError):
            continue
        if not 0 <= index < len(points):
            continue
        if isinstance(location, dict):
            latitude = location.get("latitude")
            longitude = location.get("longitude")
        elif isinstance(location, (list, tuple)) and len(location) >= 2:
            latitude, longitude = location[0], location[1]
        else:
            continue
        coordinate = _valid_coordinate(latitude, longitude)
        if coordinate is not None:
            matched[index] = coordinate
    return matched


def has_active_map_matching_viewers(pool: DatabaseConnectionPool) -> bool:
    """Return whether at least one browser map session has a live heartbeat."""
    with pool.connection() as connection:
        row = connection.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM gps.map_matching_watchers
                WHERE expires_at > CURRENT_TIMESTAMP
            )
            """
        ).fetchone()
    return bool(row and row[0])


def process_pending_map_matches(
    pool: DatabaseConnectionPool,
    api_key: str,
) -> int:
    """Match recent valid GPS history in ordered per-device batches.

    Raw coordinates remain unchanged. Matches are stored on the existing
    gps.location_history row and copied to current_state only when that exact
    fix is still the device's current/last-valid position.
    """
    query = """
        WITH recent AS (
            SELECT
                h.id, h.device_id, h.device_time,
                h.latitude, h.longitude,
                (h.matched_at IS NOT NULL) AS already_matched,
                ROW_NUMBER() OVER (
                    PARTITION BY h.device_id
                    ORDER BY h.device_time DESC, h.id DESC
                ) AS point_rank
            FROM gps.location_history AS h
            WHERE h.gps_valid IS TRUE
              AND h.latitude IS NOT NULL
              AND h.longitude IS NOT NULL
              AND h.device_time >= CURRENT_TIMESTAMP - (%s * INTERVAL '1 minute')
        )
        SELECT id, device_id, device_time, latitude, longitude, already_matched
        FROM recent
        WHERE point_rank <= %s
        ORDER BY device_id, device_time, id
    """
    with pool.connection() as connection:
        rows = connection.execute(
            query, (_RECENT_WINDOW_MINUTES, _MAX_POINTS_PER_REQUEST)
        ).fetchall()

    by_device: dict[int, list[tuple[int, object, float, float, bool]]] = defaultdict(list)
    for history_id, device_id, device_time, latitude, longitude, already_matched in rows:
        coordinate = _valid_coordinate(latitude, longitude)
        if coordinate is None:
            continue
        by_device[int(device_id)].append(
            (int(history_id), device_time, coordinate[0], coordinate[1], bool(already_matched))
        )

    saved = 0
    for device_id, history in by_device.items():
        pending_indices = [index for index, point in enumerate(history) if not point[4]]
        if len(pending_indices) < 2:
            # Batch new fixes instead of billing the API for every isolated sample.
            continue

        # Include up to two previously matched points before the first new fix,
        # so the road matcher sees a route segment instead of isolated points.
        first_pending = pending_indices[0]
        last_pending = pending_indices[-1]
        start = max(0, first_pending - 2)
        segment = history[start:last_pending + 1]
        if len(segment) < 2:
            # A single point cannot be map-matched reliably; retry after the next fix.
            continue

        request_points = [(point[0], point[2], point[3]) for point in segment]
        try:
            matches = _request_matched_points(api_key, request_points)
        except Exception:
            _LOGGER.exception(
                "Road matching failed for device_id=%s; raw GPS remains available",
                device_id,
            )
            continue

        if not matches:
            _LOGGER.warning(
                "Neshan returned no snapped points for device_id=%s; using raw GPS",
                device_id,
            )
            continue

        with pool.connection() as connection:
            with connection.transaction():
                for point_index, (latitude, longitude) in matches.items():
                    history_id, device_time, original_latitude, original_longitude, _ = segment[point_index]
                    connection.execute(
                        """
                        UPDATE gps.location_history
                        SET matched_latitude = %s,
                            matched_longitude = %s,
                            matched_geom = ST_SetSRID(
                                ST_MakePoint(%s::double precision, %s::double precision), 4326
                            ),
                            match_provider = 'neshan',
                            matched_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                          AND latitude = %s
                          AND longitude = %s
                        """,
                        (
                            latitude, longitude, longitude, latitude,
                            history_id, original_latitude, original_longitude,
                        ),
                    )
                    connection.execute(
                        """
                        UPDATE gps.current_state
                        SET matched_latitude = %s,
                            matched_longitude = %s,
                            matched_geom = ST_SetSRID(
                                ST_MakePoint(%s::double precision, %s::double precision), 4326
                            ),
                            match_provider = 'neshan',
                            matched_at = CURRENT_TIMESTAMP,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE device_id = %s
                          AND COALESCE(
                              CASE WHEN gps_valid THEN device_time ELSE last_valid_device_time END,
                              device_time
                          ) = %s
                          AND COALESCE(
                              CASE WHEN gps_valid THEN latitude ELSE last_valid_latitude END,
                              latitude
                          ) = %s
                          AND COALESCE(
                              CASE WHEN gps_valid THEN longitude ELSE last_valid_longitude END,
                              longitude
                          ) = %s
                        """,
                        (
                            latitude, longitude, longitude, latitude,
                            device_id, device_time, original_latitude, original_longitude,
                        ),
                    )
                    saved += 1

    if saved:
        _LOGGER.info("Saved %d road-matched GPS point(s)", saved)
    return saved


async def run_map_matching_worker(
    shutdown_event: asyncio.Event,
    pool: DatabaseConnectionPool,
    api_key: str | None,
    poll_seconds: float = _DEFAULT_POLL_SECONDS,
) -> None:
    """Background worker. A missing key disables matching, not GPS ingestion."""
    if not api_key:
        _LOGGER.info("Neshan map matching disabled: NESHAN_MAP_MATCHING_API_KEY is not set")
        return

    while not shutdown_event.is_set():
        started = time.monotonic()
        work_task = None
        try:
            active_viewers = await asyncio.to_thread(
                has_active_map_matching_viewers, pool
            )
            if not active_viewers:
                _LOGGER.debug("Skipping Neshan matching: no active map viewers")
            else:
                work_task = asyncio.create_task(
                    asyncio.to_thread(process_pending_map_matches, pool, api_key),
                    name="sana-neshan-map-matching-scan",
                )
                await asyncio.shield(work_task)
        except asyncio.CancelledError:
            # Let an in-flight HTTP/database scan finish before the shared pool closes.
            try:
                if work_task is not None:
                    await work_task
            finally:
                raise
        except Exception:
            _LOGGER.exception("Map-matching scan failed; GPS ingestion continues")
        delay = max(0.0, poll_seconds - (time.monotonic() - started))
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=delay)
        except asyncio.TimeoutError:
            pass
