from __future__ import annotations

import os

import psycopg
import pytest


DSN = os.getenv("SANA_GPS_TEST_DSN")
pytestmark = pytest.mark.skipif(
    not DSN,
    reason="integration test requires an explicit SANA_GPS_TEST_DSN",
)


def test_postgres_schema_keeps_only_matched_positions_and_map_watchers():
    assert DSN
    required = {
        "gps.map_matched_position",
        "gps.map_matching_watchers",
        "public.fleet_device",
        "public.fleet_devicemodel",
    }
    forbidden = {
        "gps.raw_packet",
        "gps.location_history",
        "gps.current_state",
        "gps.event",
        "gps.trip",
        "gps.geofence",
        "gps.geofence_version",
        "gps.geofence_assignment",
        "gps.vehicle_geofence_state",
        "gps.traccar_unknown_device",
        "public.fleet_gpstelemetry",
        "public.fleet_unknowngpsdata",
    }
    with psycopg.connect(DSN) as connection:
        all_tables = required | forbidden
        result = connection.execute(
            """
            SELECT table_name, to_regclass(table_name)
            FROM unnest(%s::text[]) AS table_name
            """,
            (sorted(all_tables),),
        ).fetchall()
    actual = {name: resolved for name, resolved in result}
    for table in required:
        assert actual[table] is not None, f"required table missing: {table}"
    for table in forbidden:
        assert actual[table] is None, f"obsolete raw GPS table still exists: {table}"
