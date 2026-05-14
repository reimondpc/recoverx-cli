"""Chunked streaming scanner for memory-efficient file carving.

Reads the source image in fixed-size chunks and maintains an overlap
buffer so that files spanning chunk boundaries are still detected.
Keeps memory usage bounded regardless of source image size.
"""

from __future__ import annotations

from collections.abc import Callable

from recoverx.core.utils.raw_reader import RawReader

from .base import BaseCarver, CarvedFile

DEFAULT_CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB
DEFAULT_OVERLAP = 4 * 1024 * 1024  # 4 MB


class StreamingScanner:
    """Scans a RawReader in chunks with overlap between successive windows.

    Each chunk is appended to a rolling bytearray buffer.  All registered
    carvers run against the current buffer.  After each iteration the buffer
    is trimmed to the *overlap* region so that file headers near the end of
    one chunk whose footers fall in the next chunk are still found.

    Parameters
    ----------
    reader:
        Open RawReader instance.
    carvers:
        List of carver instances to run on each window.
    chunk_size:
        Number of bytes to read per iteration.
    overlap:
        Number of bytes retained from the previous window to form the
        sliding overlap region.
    """

    def __init__(
        self,
        reader: RawReader,
        carvers: list[BaseCarver],
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_OVERLAP,
    ) -> None:
        self.reader = reader
        self.carvers = carvers
        self.chunk_size = chunk_size
        self.overlap = overlap

    def scan(
        self,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[CarvedFile]:
        """Run all carvers against the reader and return discovered files.

        Each returned ``CarvedFile`` has file-absolute byte offsets.
        """
        buffer = bytearray()
        buffer_base = 0
        file_cursor = 0
        all_results: list[CarvedFile] = []
        last_found_end = 0

        while file_cursor < self.reader.size:
            to_read = min(self.chunk_size, self.reader.size - file_cursor)
            chunk = self.reader.read_at(file_cursor, to_read)
            if not chunk:
                break
            buffer.extend(chunk)
            file_cursor += len(chunk)

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

            # Slide the window — keep only the overlap tail
            if len(buffer) > self.overlap:
                buffer = buffer[-self.overlap :]
                buffer_base = max(0, file_cursor - self.overlap)

            if progress_callback is not None:
                progress_callback(file_cursor, self.reader.size)

        return all_results
