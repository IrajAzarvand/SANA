import json
from unittest.mock import MagicMock, patch

from app.traccar.client import TraccarClient


def client():
    return TraccarClient(
        api_url="http://127.0.0.1:8082/api",
        username="reader",
        password="secret",
    )


@patch("app.traccar.client.urlopen")
def test_list_positions_reads_raw_history_from_traccar_without_database_access(urlopen):
    response = MagicMock()
    response.read.return_value = json.dumps([{
        "id": 99,
        "deviceId": 42,
        "fixTime": "2026-10-21T07:00:00.000Z",
        "latitude": 35.7,
        "longitude": 51.4,
    }]).encode()
    response.__enter__.return_value = response
    urlopen.return_value = response

    positions = client().list_positions(
        42, "2026-10-21T07:00:00.000Z", "2026-10-21T08:00:00.000Z"
    )

    url = urlopen.call_args.args[0].full_url
    assert url.startswith("http://127.0.0.1:8082/api/positions?")
    assert "deviceId=42" in url
    assert positions[0]["id"] == 99


@patch("app.traccar.client.urlopen")
def test_list_current_positions_uses_traccar_positions_endpoint(urlopen):
    response = MagicMock()
    response.read.return_value = b'[{"id": 99, "deviceId": 42}]'
    response.__enter__.return_value = response
    urlopen.return_value = response

    assert client().list_current_positions() == [{"id": 99, "deviceId": 42}]
    assert urlopen.call_args.args[0].full_url == "http://127.0.0.1:8082/api/positions"
