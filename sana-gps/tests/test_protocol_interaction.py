from dataclasses import dataclass

from app.protocols.interaction import ProtocolInteraction
from app.protocols.types import ProtocolFrame, ProtocolId, ProtocolResponse


@dataclass(frozen=True, slots=True)
class FakeInteraction:
    protocol: ProtocolId = ProtocolId.TELTONIKA

    def handle(self, frame: ProtocolFrame) -> ProtocolResponse | None:
        if frame.data == b"hello":
            return ProtocolResponse(data=b"01")
        return None


def test_protocol_response_contains_only_outbound_bytes() -> None:
    response = ProtocolResponse(data=b"01")
    assert response.data == b"01"


def test_protocol_interaction_can_return_a_generic_response() -> None:
    interaction: ProtocolInteraction = FakeInteraction()
    frame = ProtocolFrame(protocol=ProtocolId.TELTONIKA, data=b"hello")
    assert interaction.handle(frame) == ProtocolResponse(data=b"01")


def test_protocol_interaction_can_return_no_response() -> None:
    interaction: ProtocolInteraction = FakeInteraction()
    frame = ProtocolFrame(protocol=ProtocolId.TELTONIKA, data=b"other")
    assert interaction.handle(frame) is None


def test_protocol_interaction_is_independent_of_transport() -> None:
    interaction: ProtocolInteraction = FakeInteraction()
    assert interaction.protocol is ProtocolId.TELTONIKA
