from __future__ import annotations

import base64
import json
import logging
from threading import RLock
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


class TraccarAPIError(RuntimeError):
    """Raised when the Traccar API is unavailable or rejects a request."""


class TraccarClient:
    """Small standard-library client for the local Traccar REST API."""

    def __init__(
        self, *, api_url: str, username: str, password: str, timeout: float = 10.0
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout
        token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        self._authorization = f"Basic {token}"
        self._devices_by_id: dict[int, dict] = {}
        self._devices_by_unique_id: dict[str, dict] = {}
        self._cache_lock = RLock()

    def _request(self, method: str, path: str, payload: dict | None = None):
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": self._authorization,
            "Accept": "application/json",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(
            f"{self.api_url}/{path.lstrip('/')}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
                if not raw:
                    return None
                return json.loads(raw.decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read(512).decode("utf-8", errors="replace")
            raise TraccarAPIError(
                f"Traccar API {method} {path} returned HTTP {exc.code}: {detail}"
            ) from exc
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise TraccarAPIError(
                f"Traccar API {method} {path} failed: {exc.__class__.__name__}"
            ) from exc

    def list_devices(self) -> list[dict]:
        result = self._request("GET", "devices")
        if not isinstance(result, list):
            raise TraccarAPIError("Traccar API /devices returned an unexpected response")
        devices = [item for item in result if isinstance(item, dict)]
        with self._cache_lock:
            self._devices_by_id = {
                int(item["id"]): item for item in devices if item.get("id") is not None
            }
            self._devices_by_unique_id = {
                str(item["uniqueId"]).strip(): item
                for item in devices
                if item.get("uniqueId") is not None and str(item["uniqueId"]).strip()
            }
        return devices

    def create_device(self, unique_id: str) -> dict:
        identifier = unique_id.strip()
        if not identifier:
            raise ValueError("unique_id must not be empty")
        result = self._request(
            "POST", "devices", {"name": identifier, "uniqueId": identifier}
        )
        if not isinstance(result, dict):
            raise TraccarAPIError("Traccar API did not return the created device")
        with self._cache_lock:
            if result.get("id") is not None:
                self._devices_by_id[int(result["id"])] = result
            self._devices_by_unique_id[identifier] = result
        return result

    def get_device_by_id(self, device_id: int) -> dict | None:
        with self._cache_lock:
            cached = self._devices_by_id.get(device_id)
        if cached is not None:
            return cached
        result = self._request("GET", f"devices/{device_id}")
        if not isinstance(result, dict):
            return None
        with self._cache_lock:
            self._devices_by_id[device_id] = result
            if result.get("uniqueId") is not None:
                self._devices_by_unique_id[str(result["uniqueId"]).strip()] = result
        return result

    def list_positions(self, device_id: int, from_time: str, to_time: str) -> list[dict]:
        """Fetch raw history from Traccar; SANA never stores the returned raw points."""
        from urllib.parse import urlencode

        query = urlencode({"deviceId": int(device_id), "from": from_time, "to": to_time})
        result = self._request("GET", f"positions?{query}")
        if not isinstance(result, list):
            raise TraccarAPIError("Traccar API /positions returned an unexpected response")
        return [item for item in result if isinstance(item, dict)]

    def list_current_positions(self) -> list[dict]:
        """Return Traccar's current/last known position for each accessible device."""
        result = self._request("GET", "positions")
        if not isinstance(result, list):
            raise TraccarAPIError("Traccar API /positions returned an unexpected response")
        return [item for item in result if isinstance(item, dict)]
