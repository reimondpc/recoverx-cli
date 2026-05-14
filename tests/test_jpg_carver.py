"""Tests for the JPEG file carver."""

from __future__ import annotations

import pytest

from recoverx.core.carving.jpg import JPEGCarver


@pytest.fixture
def carver():
    return JPEGCarver()


_HEADER = b"\xff\xd8\xff"
_FOOTER = b"\xff\xd9"
_MIN_SIZE = 128  # must match signatures.py


def _make_jpeg_chunk(size: int, fill: int = 0xA5) -> bytes:
    """Build a minimal JPEG-like block with valid markers and *size* total bytes."""
    body_size = max(size - len(_HEADER) - len(_FOOTER), 0)
    return _HEADER + bytes([fill] * body_size) + _FOOTER


class TestJPEGCarver:
    def test_carve_finds_single_jpeg(self, carver):
        chunk = _make_jpeg_chunk(_MIN_SIZE)
        data = b"\x00" * 100 + chunk + b"\x00" * 100
        results = carver.carve(data)
        assert len(results) == 1
        assert results[0].offset_start == 100
        assert results[0].offset_end == 100 + len(chunk)
        assert results[0].signature_name == "JPEG"
        assert results[0].extension == "jpg"

    def test_carve_no_jpeg(self, carver):
        data = b"\x00" * 1024
        results = carver.carve(data)
        assert results == []

    def test_carve_multiple_jpegs(self, carver):
        c1 = _make_jpeg_chunk(_MIN_SIZE, 0xAA)
        c2 = _make_jpeg_chunk(_MIN_SIZE, 0xBB)
        data = b"\x00" * 50 + c1 + b"\x00" * 30 + c2 + b"\x00" * 50
        results = carver.carve(data)
        assert len(results) == 2
        assert results[0].offset_start == 50
        assert results[1].offset_start == 50 + len(c1) + 30

    def test_carve_min_size_filter(self, carver):
        data = _HEADER + b"\x01" * 10 + _FOOTER
        results = carver.carve(data)
        assert len(results) == 0

    def test_carve_no_footer_skips(self, carver):
        data = _HEADER + b"\x01" * 200
        results = carver.carve(data)
        assert len(results) == 0

    def test_carve_empty_data(self, carver):
        assert carver.carve(b"") == []

    def test_carve_header_at_end_no_footer(self, carver):
        data = b"\x00" * 100 + _HEADER
        results = carver.carve(data)
        assert len(results) == 0

    def test_carve_extracted_data_integrity(self, carver):
        chunk = _make_jpeg_chunk(_MIN_SIZE)
        data = b"\x00" * 50 + chunk + b"\x00" * 50
        results = carver.carve(data)
        assert len(results) == 1
        assert results[0].data == chunk
