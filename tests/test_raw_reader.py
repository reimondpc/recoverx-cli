"""Tests for the RawReader binary reader."""

from __future__ import annotations

import struct

import pytest

from recoverx.core.utils.raw_reader import RawReader


@pytest.fixture
def temp_image(tmp_path):
    """Create a small binary image for testing."""
    path = tmp_path / "test.img"
    data = struct.pack(">IIII", 0xDEADBEEF, 0xCAFEBABE, 0x12345678, 0x9ABCDEF0)
    data += b"\xff" * 512  # sector-fill padding
    path.write_bytes(data * 4)  # ~8 KB total
    return path


class TestRawReader:
    def test_open_and_close(self, temp_image):
        reader = RawReader(str(temp_image))
        reader.open()
        assert reader.is_open
        assert reader.size > 0
        reader.close()
        assert not reader.is_open

    def test_context_manager(self, temp_image):
        with RawReader(str(temp_image)) as reader:
            assert reader.is_open
            assert reader.size > 0
        assert not reader.is_open

    def test_size_and_sectors(self, temp_image):
        with RawReader(str(temp_image)) as reader:
            assert reader.size == temp_image.stat().st_size
            assert reader.sector_count == reader.size // 512

    def test_read_at(self, temp_image):
        with RawReader(str(temp_image)) as reader:
            chunk = reader.read_at(0, 4)
            assert chunk == struct.pack(">I", 0xDEADBEEF)

            chunk = reader.read_at(4, 4)
            assert chunk == struct.pack(">I", 0xCAFEBABE)

    def test_read_sector(self, temp_image):
        with RawReader(str(temp_image)) as reader:
            sector = reader.read_sector(0)
            assert len(sector) == 512

    def test_read_beyond_eof(self, temp_image):
        with RawReader(str(temp_image)) as reader:
            data = reader.read_at(reader.size, 100)
            assert data == b""

    def test_iter_sectors(self, temp_image):
        with RawReader(str(temp_image)) as reader:
            sectors = list(reader.iter_sectors(start=0, count=2))
            assert len(sectors) == 2
            for idx, data in sectors:
                assert len(data) == 512

    def test_read_not_open(self):
        reader = RawReader("/nonexistent")
        with pytest.raises(RuntimeError, match="not open"):
            reader.read_at(0, 10)
