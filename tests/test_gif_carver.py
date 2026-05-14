from __future__ import annotations

import pytest

from recoverx.core.carving.gif import GIFCarver

_HEADER_87A = b"GIF87a"
_HEADER_89A = b"GIF89a"
_FOOTER = b"\x00\x3b"
_MIN_SIZE = 43


def _make_gif(header: bytes, size: int, fill: int = 0xA5) -> bytes:
    body = max(size - len(header) - len(_FOOTER), 0)
    return header + bytes([fill] * body) + _FOOTER


@pytest.fixture
def carver():
    return GIFCarver()


class TestGIFCarver:
    def test_carve_finds_gif87a(self, carver):
        chunk = _make_gif(_HEADER_87A, _MIN_SIZE)
        data = b"\x00" * 100 + chunk + b"\x00" * 100
        results = carver.carve(data)
        assert len(results) == 1
        assert results[0].offset_start == 100
        assert results[0].signature_name == "GIF"
        assert results[0].extension == "gif"

    def test_carve_finds_gif89a(self, carver):
        chunk = _make_gif(_HEADER_89A, _MIN_SIZE)
        data = b"\x00" * 50 + chunk + b"\x00" * 50
        results = carver.carve(data)
        assert len(results) == 1
        assert results[0].signature_name == "GIF"

    def test_carve_no_gif(self, carver):
        assert carver.carve(b"\x00" * 1024) == []

    def test_carve_multiple_gifs(self, carver):
        c1 = _make_gif(_HEADER_87A, _MIN_SIZE, 0xAA)
        c2 = _make_gif(_HEADER_89A, _MIN_SIZE, 0xBB)
        data = b"\x00" * 50 + c1 + b"\x00" * 30 + c2 + b"\x00" * 50
        results = carver.carve(data)
        assert len(results) == 2

    def test_carve_min_size_filter(self, carver):
        data = _HEADER_87A + b"\x01" * 5 + _FOOTER
        assert len(carver.carve(data)) == 0

    def test_carve_empty_data(self, carver):
        assert carver.carve(b"") == []

    def test_carve_data_integrity(self, carver):
        chunk = _make_gif(_HEADER_89A, _MIN_SIZE)
        data = b"\x00" * 50 + chunk + b"\x00" * 50
        results = carver.carve(data)
        assert results[0].data == chunk
