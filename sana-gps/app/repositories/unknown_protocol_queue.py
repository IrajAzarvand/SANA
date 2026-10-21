from __future__ import annotations

from uuid import UUID

from app.database.pool import DatabaseConnectionPool


class UnknownProtocolQueueRepository:
    """Retired safety stub: unknown-device raw payloads are not retained by SANA."""

    def __init__(self, pool: DatabaseConnectionPool) -> None:
        self._pool = pool

    def check_schema(self) -> bool:
        """The old queue schema is intentionally not part of current installations."""
        return False

    def record_chunk(
        self,
        *,
        session_id: UUID,
        transport: str,
        remote_address: tuple[str, int],
        payload: bytes,
    ) -> bool:
        """Refuse raw chunks from unregistered/unknown devices."""
        return False

    def match_pending_sessions(self, identifiers: tuple[str, ...], *, limit: int = 100) -> int:
        """No queue exists to scan or classify."""
        return 0
