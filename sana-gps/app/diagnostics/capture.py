from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


class RawCapture:
    """Temporary diagnostic sink for raw transport bytes."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def write(self, *, transport: str, remote: tuple[str, int], data: bytes) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        remote_host, remote_port = remote
        with self._path.open("a", encoding="utf-8") as capture_file:
            capture_file.write("RX\n")
            capture_file.write(f"timestamp={timestamp}\n")
            capture_file.write(f"transport={transport}\n")
            capture_file.write(f"remote={remote_host}:{remote_port}\n")
            capture_file.write(f"length={len(data)}\n")
            capture_file.write(f"hex={data.hex()}\n\n")
