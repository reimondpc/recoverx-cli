from __future__ import annotations

import struct

from recoverx.core.filesystems.detector import (
    FS_UNKNOWN,
    detect_filesystem,
)


class _FakeReader:
    def __init__(self, data: bytes, size: int | None = None):
        self._data = data
        self._size = size or len(data)

    @property
    def size(self) -> int:
        return self._size

    def read_at(self, offset: int, size: int) -> bytes:
        return self._data[offset : offset + size]


class TestFilesystemDetector:
    def test_unknown(self):
        reader = _FakeReader(b"\x00" * 512, 512)
        info = detect_filesystem(reader)
        assert info.fstype == FS_UNKNOWN

    def test_empty(self):
        reader = _FakeReader(b"", 0)
        info = detect_filesystem(reader)
        assert info.fstype == FS_UNKNOWN

    def test_ntfs_detection(self):
        sector = bytearray(512)
        sector[0:3] = b"\xeb\x52\x90"
        sector[3:11] = b"NTFS    "
        struct.pack_into("<H", sector, 11, 512)
        struct.pack_into("<Q", sector, 40, 1024000)
        reader = _FakeReader(bytes(sector), 1024000 * 512)
        info = detect_filesystem(reader)
        assert info.fstype == "NTFS"

    def test_fat32_detection(self):
        sector = bytearray(512)
        sector[0:3] = b"\xeb\x58\x90"
        sector[3:11] = b"MSWIN4.1"
        struct.pack_into("<H", sector, 11, 512)
        sector[13] = 8
        struct.pack_into("<H", sector, 14, 32)
        sector[16] = 2
        struct.pack_into("<H", sector, 17, 512)
        struct.pack_into("<H", sector, 19, 0)
        sector[21] = 0xF8
        struct.pack_into("<H", sector, 22, 0)
        struct.pack_into("<H", sector, 24, 63)
        struct.pack_into("<H", sector, 26, 255)
        struct.pack_into("<I", sector, 28, 0)
        struct.pack_into("<I", sector, 32, 2048000)
        struct.pack_into("<I", sector, 36, 16000)
        reader = _FakeReader(bytes(sector), 2048000 * 512)
        info = detect_filesystem(reader)
        assert info.fstype == "FAT32"

    def test_ext4_detection(self):
        sector = bytearray(2048)
        sb = bytearray(256)
        struct.pack_into("<H", sb, 56, 0xEF53)
        struct.pack_into("<I", sb, 4, 1024000)
        struct.pack_into("<I", sb, 24, 0)
        struct.pack_into("<I", sb, 32, 8192)
        label = b"TEST_VOLUME".ljust(16, b"\x00")
        sb[120:136] = label
        sector[1024:1280] = sb
        reader = _FakeReader(bytes(sector), 1024000 * 4096)
        info = detect_filesystem(reader)
        assert info.fstype == "ext2/3/4"
