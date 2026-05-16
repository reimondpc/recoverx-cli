from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable

from recoverx.core.carving.base import BaseCarver, CarvedFile
from recoverx.core.carving.streaming import StreamingScanner
from recoverx.core.scanner.mmap_scanner import MmapScanner
from recoverx.core.scanner.threaded_scanner import ThreadedScanner
from recoverx.core.utils.raw_reader import RawReader

logger = logging.getLogger("recoverx")


class ScanStrategy(ABC):
    """Abstract scan strategy.

    Each strategy implements a different scanning approach
    (full, quick, region-specific) while sharing the same interface.
    """

    @abstractmethod
    def scan(
        self,
        reader: RawReader,
        carvers: list[BaseCarver],
        progress_callback: Callable[[int, int], None] | None = None,
        interrupt_check: Callable[[], bool] | None = None,
    ) -> list[CarvedFile]: ...


class FullScanStrategy(ScanStrategy):
    """Standard full scan — delegates to threaded/mmap/streaming."""

    def __init__(
        self,
        threads: int = 0,
        no_mmap: bool = False,
        chunk_size_mb: int = 4,
        max_bytes: int = 0,
        max_time: float = 0.0,
    ) -> None:
        self.threads = threads
        self.no_mmap = no_mmap
        self.chunk_size = chunk_size_mb * 1024 * 1024
        self.max_bytes = max_bytes
        self.max_time = max_time

    def scan(
        self,
        reader: RawReader,
        carvers: list[BaseCarver],
        progress_callback: Callable[[int, int], None] | None = None,
        interrupt_check: Callable[[], bool] | None = None,
    ) -> list[CarvedFile]:
        import os

        auto_threads = max(1, os.cpu_count() or 4) if self.threads == 0 else self.threads

        if auto_threads > 1:
            return self._threaded(reader, carvers, auto_threads, progress_callback, interrupt_check)

        path = getattr(reader, "path", "")
        if not self.no_mmap and not path.startswith("/dev/"):
            try:
                return self._mmap(reader, carvers, progress_callback, interrupt_check)
            except Exception as e:
                logger.debug("mmap failed (%s), falling back to streaming", e)

        return self._streaming(reader, carvers, progress_callback, interrupt_check)

    def _threaded(
        self,
        reader: RawReader,
        carvers: list[BaseCarver],
        num_threads: int,
        progress_callback: Callable[[int, int], None] | None = None,
        interrupt_check: Callable[[], bool] | None = None,
    ) -> list[CarvedFile]:
        scanner = ThreadedScanner(reader, carvers, num_threads=num_threads)
        if interrupt_check is not None and interrupt_check():
            return []
        return scanner.scan(progress_callback=progress_callback)

    def _mmap(
        self,
        reader: RawReader,
        carvers: list[BaseCarver],
        progress_callback: Callable[[int, int], None] | None = None,
        interrupt_check: Callable[[], bool] | None = None,
    ) -> list[CarvedFile]:
        scanner = MmapScanner(reader, carvers, chunk_size=self.chunk_size)
        if interrupt_check is not None and interrupt_check():
            return []
        return scanner.scan(progress_callback=progress_callback)

    def _streaming(
        self,
        reader: RawReader,
        carvers: list[BaseCarver],
        progress_callback: Callable[[int, int], None] | None = None,
        interrupt_check: Callable[[], bool] | None = None,
    ) -> list[CarvedFile]:
        scanner = StreamingScanner(reader, carvers, chunk_size=self.chunk_size)
        if interrupt_check is not None and interrupt_check():
            return []
        return scanner.scan(progress_callback=progress_callback)


class QuickScanStrategy(ScanStrategy):
    """Quick scan — targets high-probability regions first.

    Order:
      1. Boot sector + first 1 MB (often contains partition metadata)
      2. Last 10 MB (deleted files often linger near end)
      3. MFT region if NTFS detected
      4. Remaining space (if time allows)
    """

    QUICK_CHUNK = 4 * 1024 * 1024

    def __init__(self) -> None:
        self.max_bytes: int = 0

    def scan(
        self,
        reader: RawReader,
        carvers: list[BaseCarver],
        progress_callback: Callable[[int, int], None] | None = None,
        interrupt_check: Callable[[], bool] | None = None,
    ) -> list[CarvedFile]:
        from recoverx.core.filesystems.ntfs.boot_sector import parse_boot_sector

        limit = self.max_bytes if self.max_bytes > 0 else reader.size
        all_files: list[CarvedFile] = []
        scanned = 0
        total_to_scan = min(reader.size, limit)

        def _wrapped_cb(pos: int, total: int) -> None:
            if progress_callback is not None:
                progress_callback(scanned + pos, total_to_scan)

        def _scan_window(start: int, size: int) -> list[CarvedFile]:
            nonlocal scanned
            end = min(start + size, reader.size)
            if start >= end:
                return []
            actual_size = end - start
            scanner = StreamingScanner(
                reader,
                carvers,
                chunk_size=min(self.QUICK_CHUNK, actual_size),
            )
            result = scanner.scan(progress_callback=_wrapped_cb)
            scanned += actual_size
            return result

        if interrupt_check is not None and interrupt_check():
            return []

        region_files = _scan_window(0, 1024 * 1024)
        all_files.extend(region_files)

        if interrupt_check is not None and interrupt_check():
            return all_files

        tail_size = min(10 * 1024 * 1024, reader.size // 4)
        region_files = _scan_window(max(0, reader.size - tail_size), tail_size)
        all_files.extend(region_files)

        if interrupt_check is not None and interrupt_check():
            return all_files

        try:
            sector0 = reader.read_at(0, 512)
            bpb = parse_boot_sector(sector0)
            if bpb is not None and hasattr(bpb, "mft_cluster"):
                bytes_per_cluster = bpb.sectors_per_cluster * bpb.bytes_per_sector
                mft_offset = bpb.mft_cluster * bytes_per_cluster
                mft_size = min(16 * 1024 * 1024, reader.size - mft_offset)
                if mft_size > 0:
                    region_files = _scan_window(mft_offset, mft_size)
                    all_files.extend(region_files)

                    if interrupt_check is not None and interrupt_check():
                        return all_files
        except Exception:
            logger.debug("Quick scan: MFT detection skipped", exc_info=True)

        remaining = total_to_scan - scanned
        if remaining > 0 and scanned < limit:
            region_files = _scan_window(scanned, remaining)
            all_files.extend(region_files)

        all_files.sort(key=lambda f: f.offset_start)
        return all_files
