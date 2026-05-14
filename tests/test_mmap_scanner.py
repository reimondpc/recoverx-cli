from __future__ import annotations

import tempfile

import pytest

from recoverx.core.carving.jpg import JPEGCarver
from recoverx.core.scanner.mmap_scanner import MmapScanner
from recoverx.core.utils.raw_reader import RawReader

_HEADER = b"\xff\xd8\xff"
_FOOTER = b"\xff\xd9"


@pytest.fixture
def carvers():
    return [JPEGCarver()]


@pytest.fixture
def sample_image():
    jpeg = _HEADER + b"\xa5" * 200 + _FOOTER
    with tempfile.NamedTemporaryFile(suffix=".img", delete=False) as f:
        f.write(b"\x00" * 1000)
        f.write(jpeg)
        f.write(b"\x00" * 1000)
        f.write(jpeg)
        f.write(b"\x00" * 1000)
        fname = f.name
    yield fname


class TestMmapScanner:
    def test_scan_finds_files(self, sample_image, carvers):
        with RawReader(sample_image) as reader:
            scanner = MmapScanner(reader, carvers)
            results = scanner.scan()
            assert len(results) == 2

    def test_scan_no_files(self, carvers):
        with tempfile.NamedTemporaryFile(suffix=".img", delete=False) as f:
            f.write(b"\x00" * 4096)
            fname = f.name
        with RawReader(fname) as reader:
            scanner = MmapScanner(reader, carvers)
            results = scanner.scan()
            assert results == []

    def test_scan_empty_image(self, carvers):
        with tempfile.NamedTemporaryFile(suffix=".img", delete=False) as f:
            fname = f.name
        with RawReader(fname) as reader:
            scanner = MmapScanner(reader, carvers)
            results = scanner.scan()
            assert results == []

    def test_scan_uses_mmap(self, sample_image, carvers):
        with RawReader(sample_image) as reader:
            scanner = MmapScanner(reader, carvers)
            scanner.scan()
            assert scanner.used_mmap

    def test_scan_fallback_on_empty(self, carvers):
        with tempfile.NamedTemporaryFile(suffix=".img", delete=False) as f:
            fname = f.name
        with RawReader(fname) as reader:
            scanner = MmapScanner(reader, carvers)
            results = scanner.scan()
            assert results == []

    def test_scan_correct_offsets(self, sample_image, carvers):
        with RawReader(sample_image) as reader:
            scanner = MmapScanner(reader, carvers)
            results = scanner.scan()
            assert results[0].offset_start == 1000
            assert results[1].offset_start == 1000 + 3 + 200 + 2 + 1000

    def test_scan_with_progress(self, sample_image, carvers):
        updates = []

        def cb(pos, total):
            updates.append(pos)

        with RawReader(sample_image) as reader:
            scanner = MmapScanner(reader, carvers)
            scanner.scan(progress_callback=cb)
            assert len(updates) > 0
