"""Tests for the StreamingScanner (chunked file carving)."""

from __future__ import annotations

import pytest

from recoverx.core.carving.jpg import JPEGCarver
from recoverx.core.carving.streaming import StreamingScanner
from recoverx.core.utils.raw_reader import RawReader

_JPEG = b"\xff\xd8\xff" + b"\xaa" * 200 + b"\xff\xd9"


@pytest.fixture
def small_image(tmp_path):
    """Create a small image (~8 KB) with one embedded JPEG."""
    path = tmp_path / "small.img"
    data = bytearray(b"\x00" * 1024)
    data.extend(_JPEG)
    data.extend(b"\x00" * 1024)
    path.write_bytes(data)
    return path


class TestStreamingScanner:
    def test_basic_scan_matches_in_memory(self, small_image):
        with RawReader(str(small_image)) as reader:
            scanner = StreamingScanner(reader, [JPEGCarver()], chunk_size=512, overlap=256)
            results = scanner.scan()

            reader._handle.seek(0)
            full = reader.read_at(0, reader.size)
            expected = JPEGCarver().carve(full)

        assert len(results) == len(expected)
        assert results[0].offset_start == 1024
        assert results[0].data == _JPEG

    def test_scan_empty_image(self, tmp_path):
        path = tmp_path / "empty.img"
        path.write_bytes(b"")
        with RawReader(str(path)) as reader:
            scanner = StreamingScanner(reader, [JPEGCarver()])
            assert scanner.scan() == []

    def test_scan_no_matches(self, tmp_path):
        path = tmp_path / "noise.img"
        path.write_bytes(b"\x00" * 4096)
        with RawReader(str(path)) as reader:
            scanner = StreamingScanner(reader, [JPEGCarver()])
            assert scanner.scan() == []

    def test_file_spans_chunk_boundary(self, tmp_path):
        """JPEG that starts in one chunk and ends in the next."""
        path = tmp_path / "straddle.img"
        # Place JPEG so header is near end of first chunk
        chunk_size = 512
        jpeg_size = len(_JPEG)
        gap = chunk_size - 20  # header will be 20 bytes before chunk boundary
        data = bytearray(b"\x00" * gap)
        data.extend(_JPEG)
        data.extend(b"\x00" * chunk_size)
        path.write_bytes(data)

        with RawReader(str(path)) as reader:
            scanner = StreamingScanner(
                reader, [JPEGCarver()], chunk_size=chunk_size, overlap=jpeg_size
            )
            results = scanner.scan()
        assert len(results) == 1
        assert results[0].offset_start == gap
        assert results[0].data == _JPEG

    def test_multiple_files_in_large_image(self, tmp_path):
        path = tmp_path / "multi.img"
        jpeg2 = b"\xff\xd8\xff" + b"\xbb" * 150 + b"\xff\xd9"
        data = b"\x00" * 500 + _JPEG + b"\x00" * 300 + jpeg2 + b"\x00" * 500
        path.write_bytes(data)

        with RawReader(str(path)) as reader:
            scanner = StreamingScanner(reader, [JPEGCarver()], chunk_size=256, overlap=200)
            results = scanner.scan()
        assert len(results) == 2
        assert results[0].data == _JPEG
        assert results[1].data == jpeg2

    def test_progress_callback(self, small_image):
        with RawReader(str(small_image)) as reader:
            calls: list[tuple[int, int]] = []

            def cb(pos: int, total: int) -> None:
                calls.append((pos, total))

            scanner = StreamingScanner(reader, [JPEGCarver()], chunk_size=512, overlap=256)
            scanner.scan(progress_callback=cb)

            assert len(calls) > 0
            assert calls[-1] == (reader.size, reader.size)

    def test_multiple_carvers(self, tmp_path):
        from recoverx.core.carving.png import PNGCarver

        path = tmp_path / "mixed.img"
        png = b"\x89PNG\r\n\x1a\n" + b"\xcc" * 100 + b"\x00\x00\x00\x00IEND\xae\x42\x60\x82"
        data = bytearray(b"\x00" * 256)
        data.extend(_JPEG)
        data.extend(b"\x00" * 128)
        data.extend(png)
        data.extend(b"\x00" * 256)
        path.write_bytes(data)

        with RawReader(str(path)) as reader:
            scanner = StreamingScanner(
                reader, [JPEGCarver(), PNGCarver()], chunk_size=256, overlap=200
            )
            results = scanner.scan()
        assert len(results) == 2
        assert results[0].signature_name == "JPEG"
        assert results[1].signature_name == "PNG"
