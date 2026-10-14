from __future__ import annotations

import logging
from uuid import UUID

from app.database.pool import DatabaseConnectionPool
from app.protocols.unknown_matching import match_registered_identifiers

logger = logging.getLogger(__name__)


class UnknownProtocolQueueRepository:
    """Persist raw unknown-protocol chunks until they can be investigated safely."""

    _MAX_SESSION_BYTES = 8192
    _MAX_SESSION_CHUNKS = 128
    _MAX_TOTAL_ROWS = 100_000
    _PENDING_SESSION_IDS_SQL = """
        SELECT session_id
        FROM public.fleet_unknowngpsdata
        WHERE status = 'pending'
        GROUP BY session_id
        ORDER BY MIN(id)
        LIMIT %s
    """
    _SESSION_CHUNKS_SQL = """
        SELECT raw_payload
        FROM public.fleet_unknowngpsdata
        WHERE session_id = %s AND status = 'pending'
        ORDER BY id
    """
    _MARK_MATCHED_SQL = """
        UPDATE public.fleet_unknowngpsdata
        SET status = 'matched', identifier_candidate = %s
        WHERE session_id = %s AND status = 'pending'
    """

    def __init__(self, pool: DatabaseConnectionPool) -> None:
        self._pool = pool

    def record_chunk(
        self,
        *,
        session_id: UUID,
        transport: str,
        remote_address: tuple[str, int],
        payload: bytes,
    ) -> bool:
        """Persist one chunk if per-session and global safety limits allow it."""
        if not payload or len(payload) > self._MAX_SESSION_BYTES:
            return False
        remote = f"{remote_address[0]}:{remote_address[1]}"
        sql = """
            INSERT INTO public.fleet_unknowngpsdata
                (session_id, transport, remote_address, raw_payload,
                 identifier_candidate, status, received_at)
            SELECT %s, %s, %s, %s,
                   COALESCE((
                       SELECT identifier_candidate
                       FROM public.fleet_unknowngpsdata
                       WHERE session_id = %s AND status = 'matched'
                       ORDER BY id
                       LIMIT 1
                   ), ''),
                   CASE WHEN EXISTS (
                       SELECT 1 FROM public.fleet_unknowngpsdata
                       WHERE session_id = %s AND status = 'matched'
                   ) THEN 'matched' ELSE 'pending' END,
                   NOW()
            WHERE
                (SELECT COALESCE(SUM(OCTET_LENGTH(raw_payload)), 0)
                 FROM public.fleet_unknowngpsdata
                 WHERE session_id = %s) + OCTET_LENGTH(%s) <= %s
                AND
                (SELECT COUNT(*)
                 FROM public.fleet_unknowngpsdata
                 WHERE session_id = %s) < %s
                AND
                (SELECT COUNT(*) FROM public.fleet_unknowngpsdata) < %s
            RETURNING id
        """
        with self._pool.connection() as connection:
            row = connection.execute(
                sql,
                (
                    str(session_id), transport, remote, bytes(payload),
                    str(session_id), str(session_id),
                    str(session_id), bytes(payload), self._MAX_SESSION_BYTES,
                    str(session_id), self._MAX_SESSION_CHUNKS, self._MAX_TOTAL_ROWS,
                ),
            ).fetchone()
        if row is None:
            logger.warning(
                "Unknown GPS data was not queued because a storage limit was reached "
                "(session=%s, bytes=%d)",
                session_id,
                len(payload),
            )
            return False
        return True

    def match_pending_sessions(self, identifiers: tuple[str, ...], *, limit: int = 100) -> int:
        """Match pending raw streams against current registered device identifiers.

        A match only changes the queue status. It never changes fleet_device.protocol
        and never inserts raw unknown data into telemetry tables.
        """
        if not identifiers:
            return 0
        with self._pool.connection() as connection:
            rows = connection.execute(self._PENDING_SESSION_IDS_SQL, (limit,)).fetchall()
        matched = 0
        for (session_id,) in rows:
            with self._pool.connection() as connection:
                chunks = connection.execute(
                    self._SESSION_CHUNKS_SQL, (session_id,)
                ).fetchall()
            payload = bytearray()
            truncated = False
            for (chunk,) in chunks:
                chunk = bytes(chunk)
                if len(payload) + len(chunk) > self._MAX_SESSION_BYTES:
                    truncated = True
                    break
                payload.extend(chunk)
            if truncated:
                continue
            candidates = match_registered_identifiers(bytes(payload), identifiers)
            if not candidates:
                continue
            # One stream should identify one device. Ambiguous matches remain pending
            # for a later, more specific framing/identifier strategy.
            if len(candidates) != 1:
                logger.info(
                    "Unknown GPS stream session %s matched multiple registered identifiers; "
                    "leaving it pending",
                    session_id,
                )
                continue
            with self._pool.connection() as connection:
                connection.execute(
                    self._MARK_MATCHED_SQL, (candidates[0], session_id)
                )
            matched += 1
            logger.info(
                "Unknown GPS stream session %s matched registered identifier %s; "
                "raw data retained for protocol verification",
                session_id,
                candidates[0],
            )
        return matched
