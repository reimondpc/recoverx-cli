from __future__ import annotations

import struct

import pytest

from recoverx.core.carving.bmp import BMPCarver

_MIN_SIZE = 54


def _make_bmp(size: int, fill: int = 0xA5) -> bytes:
    header = b"BM"
    body = max(size - len(header) - 4, _MIN_SIZE - len(header))
    total_size = len(header) + body
    return header + struct.pack("<I", total_size) + bytes([fill] * (body - 4))  # -4 for size field


@pytest.fixture
def carver():
    return BMPCarver()


class TestBMPCarver:
    def test_carve_finds_bmp(self, carver):
        chunk = _make_bmp(128)
        data = b"\x00" * 100 + chunk + b"\x00" * 100
        results = carver.carve(data)
        assert len(results) == 1
        assert results[0].offset_start == 100
        assert results[0].signature_name == "BMP"
        assert results[0].extension == "bmp"

    def test_carve_no_bmp(self, carver):
        assert carver.carve(b"\x00" * 1024) == []

    def test_carve_multiple_bmps(self, carver):
        c1 = _make_bmp(128, 0xAA)
        c2 = _make_bmp(128, 0xBB)
        data = b"\x00" * 50 + c1 + b"\x00" * 30 + c2 + b"\x00" * 50
        results = carver.carve(data)
        assert len(results) == 2

    def test_carve_min_size_filter(self, carver):
        data = b"BM" + struct.pack("<I", 10) + b"\x01" * 6
        results = carver.carve(data)
        assert len(results) == 0

    def test_carve_declared_size(self, carver):
        declared = 200
        body = b"\xa5" * (declared - 6)
        data = b"BM" + struct.pack("<I", declared) + body
        results = carver.carve(data)
        assert len(results) == 1
        assert len(results[0].data) == declared

    def test_carve_empty_data(self, carver):
        assert carver.carve(b"") == []

    def test_carve_data_integrity(self, carver):
        chunk = _make_bmp(128)
        data = b"\x00" * 50 + chunk + b"\x00" * 50
        results = carver.carve(data)
        assert results[0].data == chunk
