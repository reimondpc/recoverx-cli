from __future__ import annotations

import tempfile

import pytest

from recoverx.core.carving.jpg import JPEGCarver
from recoverx.core.scanner.threaded_scanner import ThreadedScanner
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
        for _ in range(10):
            f.write(b"\x00" * 500)
            f.write(jpeg)
        fname = f.name
    yield fname


class TestThreadedScanner:
    def test_scan_finds_files(self, sample_image, carvers):
        with RawReader(sample_image) as reader:
            scanner = ThreadedScanner(reader, carvers, num_threads=2)
            results = scanner.scan()
            assert len(results) == 10

    def test_scan_no_files(self, carvers):
        with tempfile.NamedTemporaryFile(suffix=".img", delete=False) as f:
            f.write(b"\x00" * 4096)
            fname = f.name
        with RawReader(fname) as reader:
            scanner = ThreadedScanner(reader, carvers, num_threads=2)
            results = scanner.scan()
            assert results == []

    def test_scan_single_thread(self, sample_image, carvers):
        with RawReader(sample_image) as reader:
            scanner = ThreadedScanner(reader, carvers, num_threads=1)
            results = scanner.scan()
            assert len(results) == 10

    def test_scan_correct_offsets(self, sample_image, carvers):
        with RawReader(sample_image) as reader:
            scanner = ThreadedScanner(reader, carvers, num_threads=2)
            results = scanner.scan()
            results.sort(key=lambda f: f.offset_start)
            assert results[0].offset_start >= 0
            for i in range(1, len(results)):
                assert results[i].offset_start > results[i - 1].offset_end

    def test_scan_tracks_thread_times(self, sample_image, carvers):
        with RawReader(sample_image) as reader:
            scanner = ThreadedScanner(reader, carvers, num_threads=2)
            scanner.scan()
            assert len(scanner.per_thread_times) > 0

    def test_scan_empty_image(self, carvers):
        with tempfile.NamedTemporaryFile(suffix=".img", delete=False) as f:
            fname = f.name
        with RawReader(fname) as reader:
            scanner = ThreadedScanner(reader, carvers, num_threads=4)
            results = scanner.scan()
            assert results == []

    def test_scan_partition_small_image(self, carvers):
        with tempfile.NamedTemporaryFile(suffix=".img", delete=False) as f:
            f.write(b"\x00" * 100)
            fname = f.name
        with RawReader(fname) as reader:
            scanner = ThreadedScanner(reader, carvers, num_threads=4)
            results = scanner.scan()
            assert isinstance(results, list)
