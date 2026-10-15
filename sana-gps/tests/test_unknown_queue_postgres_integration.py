from __future__ import annotations

import os
import uuid
from pathlib import Path

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict

from app.config import DatabaseConfig
from app.database.pool import DatabaseConnectionPool
from app.repositories.unknown_protocol_queue import UnknownProtocolQueueRepository


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return values
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if separator and key.strip():
            values[key.strip()] = value.strip().strip("'\"")
    return values


GPS_ENV = _read_env_file(PROJECT_ROOT / "sana-gps" / ".env")
BACKEND_ENV = _read_env_file(PROJECT_ROOT / "sana-backend" / ".env")


def _env_value(name: str, default: str = "") -> str:
    return (
        os.getenv(name)
        or GPS_ENV.get(name)
        or BACKEND_ENV.get(name)
        or default
    )


def _make_dsn(*, user: str, password: str) -> str | None:
    database = _env_value("SANA_GPS_DB_NAME") or _env_value("DB_NAME")
    if not database or not user or not password:
        return None
    from psycopg.conninfo import make_conninfo

    return make_conninfo(
        host=_env_value("SANA_GPS_DB_HOST", _env_value("DB_HOST", "127.0.0.1")),
        port=_env_value("SANA_GPS_DB_PORT", _env_value("DB_PORT", "5432")),
        dbname=database,
        user=user,
        password=password,
    )


DSN = os.getenv("SANA_GPS_TEST_DSN") or _make_dsn(
    user=_env_value("SANA_GPS_TEST_USER", _env_value("SANA_GPS_DB_USER", _env_value("DB_USER", "sana_user"))),
    password=_env_value("SANA_GPS_TEST_PASSWORD", _env_value("SANA_GPS_DB_PASSWORD", _env_value("DB_PASSWORD"))),
)
ADMIN_DSN = os.getenv("SANA_GPS_TEST_ADMIN_DSN")

pytestmark = pytest.mark.skipif(
    not DSN or not ADMIN_DSN,
    reason="requires runtime and test-admin PostgreSQL DSNs",
)


def test_unknown_queue_postgres_persistence_and_recheck_isolated() -> None:
    assert DSN and ADMIN_DSN
    session_id = uuid.uuid4()
    # A valid-length numeric identifier makes the test stream representative
    # while keeping the device and queue rows unique to this run.
    imei = "9" + uuid.uuid4().hex[:14]
    first_chunk = f"*HQ,{imei[:7]}".encode("ascii")
    second_chunk = f"{imei[7:]},V1#".encode("ascii")
    device_id: int | None = None
    pool: DatabaseConnectionPool | None = None

    try:
        with psycopg.connect(ADMIN_DSN) as connection:
            row = connection.execute(
                """
                INSERT INTO public.fleet_device
                    (imei, protocol, sim_number, management_status, created_at, updated_at)
                VALUES (%s, '', '', 'warehouse', NOW(), NOW())
                RETURNING id
                """,
                (imei,),
            ).fetchone()
            assert row is not None
            device_id = int(row[0])

        params = conninfo_to_dict(DSN)
        config = DatabaseConfig(
            host=params.get("host", "127.0.0.1"),
            port=int(params.get("port", "5432")),
            name=params["dbname"],
            user=params["user"],
            password=params.get("password", ""),
            pool_min_size=1,
            pool_max_size=2,
        )
        pool = DatabaseConnectionPool(config)
        pool.open()
        repository = UnknownProtocolQueueRepository(pool)

        assert repository.check_schema() is None
        assert repository.record_chunk(
            session_id=session_id,
            transport="tcp",
            remote_address=("192.0.2.55", 43120),
            payload=first_chunk,
        )
        assert repository.record_chunk(
            session_id=session_id,
            transport="tcp",
            remote_address=("192.0.2.55", 43120),
            payload=second_chunk,
        )

        # Read through the runtime role, proving the rows are committed and visible.
        with psycopg.connect(DSN) as connection:
            persisted = connection.execute(
                """
                SELECT raw_payload, status, identifier_candidate, transport, remote_address
                FROM public.fleet_unknowngpsdata
                WHERE session_id = %s
                ORDER BY id
                """,
                (session_id,),
            ).fetchall()
        assert [bytes(row[0]) for row in persisted] == [first_chunk, second_chunk]
        assert [row[1] for row in persisted] == ["pending", "pending"]
        assert [row[2] for row in persisted] == ["", ""]
        assert all(row[3] == "tcp" for row in persisted)
        assert all(row[4] == "192.0.2.55:43120" for row in persisted)

        # The same production matching method should match the reassembled stream.
        assert repository.match_pending_sessions((imei,)) == 1
        with psycopg.connect(DSN) as connection:
            matched = connection.execute(
                """
                SELECT raw_payload, status, identifier_candidate
                FROM public.fleet_unknowngpsdata
                WHERE session_id = %s
                ORDER BY id
                """,
                (session_id,),
            ).fetchall()
        assert [bytes(row[0]) for row in matched] == [first_chunk, second_chunk]
        assert [row[1] for row in matched] == ["matched", "matched"]
        assert [row[2] for row in matched] == [imei, imei]

        # Matching unknown data is not protocol registration and must not create
        # normal telemetry/current-state/history records.
        with psycopg.connect(ADMIN_DSN) as connection:
            device = connection.execute(
                "SELECT protocol FROM public.fleet_device WHERE id = %s AND imei = %s",
                (device_id, imei),
            ).fetchone()
            assert device == ("",)
            for table in (
                "gps.raw_packet",
                "gps.location_history",
                "gps.current_state",
            ):
                count = connection.execute(
                    f"SELECT count(*) FROM {table} WHERE device_id = %s",
                    (device_id,),
                ).fetchone()[0]
                assert count == 0, f"Unexpected telemetry row in {table}"
    finally:
        if pool is not None:
            pool.close()
        # Remove only rows belonging to this test's UUID and its uniquely-created device.
        with psycopg.connect(ADMIN_DSN) as connection:
            with connection.transaction():
                connection.execute(
                    "DELETE FROM public.fleet_unknowngpsdata WHERE session_id = %s",
                    (session_id,),
                )
                if device_id is not None:
                    connection.execute(
                        "DELETE FROM public.fleet_device WHERE id = %s AND imei = %s",
                        (device_id, imei),
                    )
                remaining = connection.execute(
                    "SELECT count(*) FROM public.fleet_unknowngpsdata WHERE session_id = %s",
                    (session_id,),
                ).fetchone()[0]
                assert remaining == 0
