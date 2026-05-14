from __future__ import annotations

import logging
import mmap
from collections.abc import Callable

from recoverx.core.carving.base import BaseCarver, CarvedFile
from recoverx.core.carving.streaming import StreamingScanner
from recoverx.core.utils.raw_reader import RawReader

logger = logging.getLogger("recoverx")

MMAP_CHUNK_SIZE = 256 * 1024 * 1024
OVERLAP_SIZE = 4 * 1024 * 1024


class MmapScanner:
    def __init__(
        self,
        reader: RawReader,
        carvers: list[BaseCarver],
        chunk_size: int = MMAP_CHUNK_SIZE,
        overlap: int = OVERLAP_SIZE,
    ) -> None:
        self.reader = reader
        self.carvers = carvers
        self.chunk_size = chunk_size
        self.overlap = overlap
        self._used_mmap = False

    @property
    def used_mmap(self) -> bool:
        return self._used_mmap

    def scan(
        self,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[CarvedFile]:
        fd = self._get_fileno()
        if fd is not None:
            try:
                return self._scan_mmap(fd, progress_callback)
            except (OSError, ValueError) as e:
                logger.warning("mmap failed (%s), falling back to streaming", e)

        return self._scan_streaming(progress_callback)

    def _get_fileno(self) -> int | None:
        try:
            return self.reader._handle.fileno() if self.reader._handle else None
        except (OSError, AttributeError):
            return None

    def _scan_mmap(
        self,
        fd: int,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[CarvedFile]:
        self._used_mmap = True
        size = self.reader.size
        all_results: list[CarvedFile] = []
        last_found_end = 0
        buffer = bytearray()
        buffer_base = 0
        file_pos = 0

        while file_pos < size:
            map_size = min(self.chunk_size, size - file_pos)

            try:
                with mmap.mmap(fd, map_size, offset=file_pos, access=mmap.ACCESS_READ) as m:
                    chunk = m.read(map_size)
            except OSError as e:
                logger.warning("mmap chunk at %d failed (%s), retrying with read", file_pos, e)
                chunk = self.reader.read_at(file_pos, map_size)

            buffer.extend(chunk)
            file_pos += len(chunk)

            data = bytes(buffer)
            for carver in self.carvers:
                for result in carver.carve(data):
                    abs_start = buffer_base + result.offset_start
                    abs_end = buffer_base + result.offset_end

                    if abs_start < last_found_end:
                        continue

                    all_results.append(
                        CarvedFile(
                            data=result.data,
                            offset_start=abs_start,
                            offset_end=abs_end,
                            signature_name=result.signature_name,
                            extension=result.extension,
                        )
                    )
                    last_found_end = abs_end

            if len(buffer) > self.overlap:
                buffer = buffer[-self.overlap :]
                buffer_base = max(0, file_pos - self.overlap)

            if progress_callback is not None:
                progress_callback(file_pos, size)

        return all_results

    def _scan_streaming(
        self,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[CarvedFile]:
        ss = StreamingScanner(
            self.reader,
            self.carvers,
            chunk_size=self.chunk_size,
            overlap=self.overlap,
        )
        return ss.scan(progress_callback=progress_callback)
