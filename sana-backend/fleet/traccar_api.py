from __future__ import annotations

import base64
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings


class TraccarAPIError(RuntimeError):
    """Raised when the configured Traccar REST API cannot serve a request."""


def traccar_request(path: str, *, params: dict | None = None):
    base_url = str(getattr(settings, "TRACCAR_API_URL", "") or "").rstrip("/")
    username = str(getattr(settings, "TRACCAR_API_USERNAME", "") or "")
    password = str(getattr(settings, "TRACCAR_API_PASSWORD", "") or "")
    if not base_url or not username or not password:
        raise TraccarAPIError("Traccar API connection is not configured")
    query = f"?{urlencode(params)}" if params else ""
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    request = Request(
        f"{base_url}/{path.lstrip('/')}{query}",
        headers={"Authorization": f"Basic {token}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=8.0) as response:
            payload = response.read()
            return json.loads(payload.decode("utf-8")) if payload else None
    except HTTPError as exc:
        raise TraccarAPIError(f"Traccar API returned HTTP {exc.code}") from exc
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise TraccarAPIError(f"Traccar API request failed: {exc.__class__.__name__}") from exc


def traccar_devices() -> list[dict]:
    result = traccar_request("devices")
    if not isinstance(result, list):
        raise TraccarAPIError("Traccar /devices returned an unexpected response")
    return [item for item in result if isinstance(item, dict)]


def traccar_current_positions() -> list[dict]:
    result = traccar_request("positions")
    if not isinstance(result, list):
        raise TraccarAPIError("Traccar /positions returned an unexpected response")
    return [item for item in result if isinstance(item, dict)]


def traccar_device_positions(device_id: int, start: str, end: str) -> list[dict]:
    result = traccar_request(
        "positions",
        params={"deviceId": int(device_id), "from": start, "to": end},
    )
    if not isinstance(result, list):
        raise TraccarAPIError("Traccar position history returned an unexpected response")
    return [item for item in result if isinstance(item, dict)]
