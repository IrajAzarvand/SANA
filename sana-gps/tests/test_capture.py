from pathlib import Path

from app.diagnostics.capture import RawCapture


def test_raw_capture_writes_transport_metadata_and_hex(tmp_path: Path):
    path = tmp_path / "capture.log"
    capture = RawCapture(path)

    capture.write(
        transport="tcp",
        remote=("203.0.113.10", 54321),
        data=b"\x00\x0f352094082143253",
    )

    text = path.read_text(encoding="utf-8")
    assert "RX\n" in text
    assert "transport=tcp\n" in text
    assert "remote=203.0.113.10:54321\n" in text
    assert "length=17\n" in text
    assert "hex=000f333532303934303832313433323533\n" in text
