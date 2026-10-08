from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.protocols.types import ProtocolFrame, ProtocolId


@dataclass(frozen=True, slots=True)
class ProtocolResponse:
    """Protocol-defined bytes that should be sent back to a device."""

    data: bytes

    def __post_init__(self) -> None:
        if not self.data:
            raise ValueError("ProtocolResponse data must not be empty")


class ProtocolInteraction(Protocol):
    """Protocol-specific interaction boundary for framed device messages."""

    @property
    def protocol(self) -> ProtocolId:
        ...

    def handle(self, frame: ProtocolFrame) -> ProtocolResponse | None:
        """Handle one complete protocol frame and optionally produce a response."""
        ...
