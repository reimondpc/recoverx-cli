"""Raw binary reader for disk images and block devices.

All operations are read-only. Supports sector-level and offset-level reads,
enabling efficient scanning of large disk images without loading them entirely
into memory.
"""

from __future__ import annotations

import os
from typing import IO


class RawReader:
    """Read-only binary reader for disk images (.img, .dd, .raw) and block devices.

    Usage:
        with RawReader("/path/to/image.img") as reader:
            sector_data = reader.read_sector(100)
            custom_data = reader.read_at(51200, 1024)
    """

    def __init__(self, path: str, sector_size: int = 512) -> None:
        self.path = path
        self.sector_size = sector_size
        self._handle: IO[bytes] | None = None
        self._size: int = 0

    def open(self) -> RawReader:
        self._handle = open(self.path, "rb")
        self._handle.seek(0, os.SEEK_END)
        self._size = self._handle.tell()
        self._handle.seek(0)
        return self

    def close(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None

    def __enter__(self) -> RawReader:
        return self.open()

    def __exit__(self, *args: object) -> None:
        self.close()

    @property
    def is_open(self) -> bool:
        return self._handle is not None

    @property
    def size(self) -> int:
        return self._size

    @property
    def sector_count(self) -> int:
        return self._size // self.sector_size

    def read_at(self, offset: int, size: int) -> bytes:
        if self._handle is None:
            raise RuntimeError("RawReader is not open. Use the context manager or call .open().")
        self._handle.seek(offset)
        return self._handle.read(size)

    def read_sector(self, sector: int) -> bytes:
        return self.read_at(sector * self.sector_size, self.sector_size)

    def iter_sectors(self, start: int = 0, count: int | None = None):
        total = self.sector_count
        end = min(start + count, total) if count is not None else total
        for i in range(start, end):
            yield i, self.read_sector(i)
