from __future__ import annotations

from collections.abc import Iterable

from app.database.pool import DatabaseConnectionPool
from app.processing.telemetry import NormalizedTelemetry


class GPSTelemetryRepository:
    """Deprecated safety guard: raw GPS telemetry belongs exclusively to Traccar.

    Kept temporarily so legacy decoder/handler modules fail explicitly rather
    than silently recreating duplicate telemetry storage. The production GPS
    runtime does not instantiate these legacy handlers.
    """

    def __init__(self, pool: DatabaseConnectionPool) -> None:
        self._pool = pool

    @staticmethod
    def _reject_raw_storage() -> None:
        raise RuntimeError(
            "SANA no longer stores raw GPS telemetry. Send device data to Traccar "
            "and read it through the Traccar API."
        )

    def save(self, *args, **kwargs) -> None:
        self._reject_raw_storage()

    def save_batch(
        self,
        records: Iterable[NormalizedTelemetry],
        *,
        protocol: str,
        raw_payload: bytes,
    ) -> int:
        self._reject_raw_storage()
