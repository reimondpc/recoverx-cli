from __future__ import annotations

import pytest

from recoverx.core.carving.pdf import PDFCarver

_HEADER = b"%PDF"
_FOOTER = b"%%EOF"
_MIN_SIZE = 1024


def _make_pdf(size: int, fill: int = 0xA5) -> bytes:
    body = max(size - len(_HEADER) - len(_FOOTER), 0)
    return _HEADER + bytes([fill] * body) + _FOOTER


@pytest.fixture
def carver():
    return PDFCarver()


class TestPDFCarver:
    def test_carve_finds_pdf(self, carver):
        chunk = _make_pdf(_MIN_SIZE)
        data = b"\x00" * 100 + chunk + b"\x00" * 100
        results = carver.carve(data)
        assert len(results) == 1
        assert results[0].offset_start == 100
        assert results[0].signature_name == "PDF"
        assert results[0].extension == "pdf"

    def test_carve_no_pdf(self, carver):
        assert carver.carve(b"\x00" * 1024) == []

    def test_carve_multiple_pdfs(self, carver):
        c1 = _make_pdf(_MIN_SIZE, 0xAA)
        c2 = _make_pdf(_MIN_SIZE, 0xBB)
        data = b"\x00" * 50 + c1 + b"\x00" * 30 + c2 + b"\x00" * 50
        results = carver.carve(data)
        assert len(results) == 2

    def test_carve_min_size_filter(self, carver):
        data = _HEADER + b"\x01" * 50 + _FOOTER
        assert len(carver.carve(data)) == 0

    def test_carve_no_footer_skips(self, carver):
        assert len(carver.carve(_HEADER + b"\x01" * (_MIN_SIZE + 100))) == 0

    def test_carve_empty_data(self, carver):
        assert carver.carve(b"") == []

    def test_carve_data_integrity(self, carver):
        chunk = _make_pdf(_MIN_SIZE)
        data = b"\x00" * 50 + chunk + b"\x00" * 50
        results = carver.carve(data)
        assert results[0].data == chunk
