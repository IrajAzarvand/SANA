from __future__ import annotations

import asyncio
import hmac
import json
import logging

from app.traccar.position_receiver import TraccarPositionReceiver

logger = logging.getLogger(__name__)
_MAX_REQUEST_BYTES = 1_048_576


class TraccarWebhookServer:
    """Minimal authenticated HTTP/1.1 endpoint for Traccar's JSON forwarder."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        secret: str,
        receiver: TraccarPositionReceiver,
    ) -> None:
        if not secret:
            raise ValueError("webhook secret must not be empty")
        self.host = host
        self.port = port
        self._secret = secret
        self._receiver = receiver
        self._server: asyncio.AbstractServer | None = None

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._handle_client, self.host, self.port, limit=65536
        )

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        status = 500
        response_body = b'{"error":"internal_error"}'
        try:
            request_line = await asyncio.wait_for(reader.readline(), timeout=5)
            parts = request_line.decode("ascii", errors="replace").strip().split()
            if len(parts) != 3:
                status, response_body = 400, b'{"error":"bad_request"}'
            else:
                method, path, _version = parts
                headers: dict[str, str] = {}
                total_header_bytes = 0
                while True:
                    line = await asyncio.wait_for(reader.readline(), timeout=5)
                    total_header_bytes += len(line)
                    if total_header_bytes > 32768:
                        raise ValueError("headers too large")
                    if line in (b"\r\n", b"\n", b""):
                        break
                    decoded = line.decode("latin-1").strip()
                    if ":" in decoded:
                        key, value = decoded.split(":", 1)
                        headers[key.strip().lower()] = value.strip()
                if method != "POST" or path.split("?", 1)[0] != "/traccar/positions":
                    status, response_body = 404, b'{"error":"not_found"}'
                else:
                    authorization = headers.get("authorization", "")
                    expected = f"Bearer {self._secret}"
                    if not hmac.compare_digest(authorization, expected):
                        status, response_body = 401, b'{"error":"unauthorized"}'
                    else:
                        try:
                            content_length = int(headers.get("content-length", "0"))
                        except ValueError:
                            content_length = 0
                        if content_length <= 0 or content_length > _MAX_REQUEST_BYTES:
                            status, response_body = 413, b'{"error":"invalid_content_length"}'
                        else:
                            body = await asyncio.wait_for(reader.readexactly(content_length), timeout=10)
                            payload = json.loads(body.decode("utf-8"))
                            result = await asyncio.to_thread(self._receiver.receive_payload, payload)
                            status = 200
                            response_body = json.dumps(result).encode("utf-8")
        except (asyncio.TimeoutError, asyncio.IncompleteReadError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            status, response_body = 400, b'{"error":"invalid_request"}'
        except Exception:
            logger.exception("Traccar webhook request failed")
        finally:
            phrases = {200: "OK", 400: "Bad Request", 401: "Unauthorized", 404: "Not Found", 413: "Payload Too Large", 500: "Internal Server Error"}
            writer.write(
                f"HTTP/1.1 {status} {phrases.get(status, 'Error')}\r\n"
                f"Content-Type: application/json\r\n"
                f"Content-Length: {len(response_body)}\r\n"
                "Connection: close\r\n\r\n".encode("ascii")
                + response_body
            )
            try:
                await writer.drain()
            except (ConnectionError, OSError):
                pass
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, OSError):
                pass
