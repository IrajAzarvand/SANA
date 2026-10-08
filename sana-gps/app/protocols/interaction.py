from __future__ import annotations

from typing import Protocol

from app.protocols.types import ProtocolFrame, ProtocolId, ProtocolResponse


class ProtocolInteraction(Protocol):
    """Protocol-specific interaction boundary for framed device messages."""

    @property
    def protocol(self) -> ProtocolId:
        ...

    def handle(self, frame: ProtocolFrame) -> ProtocolResponse | None:
        """Handle one complete protocol frame and optionally produce a response."""
        ...
