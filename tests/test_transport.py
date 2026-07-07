"""Tests for the HTTP-range-backed reader used to extract Entur stops."""

import io
import zipfile

import pytest

from telttur import transport
from telttur.transport import _HttpRangeReader

_PAYLOAD = bytes(range(256)) * 4  # 1024 bytes of known content


class _FakeResponse:
    def __init__(self, content: bytes, headers: dict[str, str]) -> None:
        self.content = content
        self.headers = headers

    def raise_for_status(self) -> None:
        pass


class _FakeRequests:
    """Serves a bytes payload through head() and Range-header get()."""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def head(self, url: str, timeout: float) -> _FakeResponse:
        return _FakeResponse(b"", {"Content-Length": str(len(self._payload))})

    def get(self, url: str, headers: dict[str, str], timeout: float) -> _FakeResponse:
        byte_range = headers["Range"].removeprefix("bytes=")
        start_s, end_s = byte_range.split("-")
        start, end = int(start_s), int(end_s)
        return _FakeResponse(self._payload[start : end + 1], {})


@pytest.fixture
def reader(monkeypatch) -> _HttpRangeReader:
    monkeypatch.setattr(transport, "requests", _FakeRequests(_PAYLOAD))
    return _HttpRangeReader("http://example.test/data.zip", timeout_s=1.0)


def test_read_slice(reader: _HttpRangeReader) -> None:
    assert reader.read(4) == _PAYLOAD[:4]
    assert reader.tell() == 4
    assert reader.read(4) == _PAYLOAD[4:8]


def test_read_all_from_position(reader: _HttpRangeReader) -> None:
    reader.seek(1000)
    assert reader.read(-1) == _PAYLOAD[1000:]


def test_read_past_end_returns_empty(reader: _HttpRangeReader) -> None:
    reader.seek(0, io.SEEK_END)
    assert reader.read(10) == b""


def test_seek_whence_semantics(reader: _HttpRangeReader) -> None:
    assert reader.seek(10) == 10
    assert reader.seek(5, io.SEEK_CUR) == 15
    assert reader.seek(-24, io.SEEK_END) == len(_PAYLOAD) - 24
    assert reader.tell() == len(_PAYLOAD) - 24


def test_read_clamps_to_size(reader: _HttpRangeReader) -> None:
    reader.seek(-4, io.SEEK_END)
    assert reader.read(100) == _PAYLOAD[-4:]


def test_zipfile_can_extract_member_via_range_reader(monkeypatch) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("stops.txt", "stop_lat,stop_lon\n59.9,10.7\n")
        zf.writestr("other.txt", "x" * 10_000)
    payload = buf.getvalue()

    monkeypatch.setattr(transport, "requests", _FakeRequests(payload))
    reader = _HttpRangeReader("http://example.test/gtfs.zip", timeout_s=1.0)
    with zipfile.ZipFile(reader) as zf, zf.open("stops.txt") as member:
        assert member.read() == b"stop_lat,stop_lon\n59.9,10.7\n"
