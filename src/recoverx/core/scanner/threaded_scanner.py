from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass

from recoverx.core.carving.base import BaseCarver, CarvedFile
from recoverx.core.utils.raw_reader import RawReader

logger = logging.getLogger("recoverx")

DEFAULT_THREADS = 4
REGION_OVERLAP = 4 * 1024 * 1024


@dataclass
class ScanRegion:
    start: int
    end: int
    region_id: int


@dataclass
class RegionResult:
    region_id: int
    files: list[CarvedFile]
    elapsed: float


class ThreadedScanner:
    def __init__(
        self,
        reader: RawReader,
        carvers: list[BaseCarver],
        num_threads: int = DEFAULT_THREADS,
        overlap: int = REGION_OVERLAP,
    ) -> None:
        self.reader = reader
        self.carvers = carvers
        self.num_threads = max(1, min(num_threads, 64))
        self.overlap = overlap
        self._per_thread_times: list[tuple[int, float]] = []

    @property
    def per_thread_times(self) -> list[tuple[int, float]]:
        return list(self._per_thread_times)

    def scan(
        self,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[CarvedFile]:
        size = self.reader.size
        regions = self._partition(size)

        lock = threading.Lock()
        completed = [0]
        total = size

        def _progress(region: ScanRegion, pos: int, _total: int) -> None:
            with lock:
                completed[0] += pos - (completed[0] if completed[0] < total else 0)
                if progress_callback is not None:
                    progress_callback(min(completed[0], total), total)

        threads: list[threading.Thread] = []
        region_results: list[RegionResult | None] = [None] * len(regions)

        def _scan_region(region: ScanRegion) -> None:
            import time

            t0 = time.perf_counter()
            local_files = self._scan_region_data(region, _progress)
            elapsed = time.perf_counter() - t0
            region_results[region.region_id] = RegionResult(
                region_id=region.region_id,
                files=local_files,
                elapsed=elapsed,
            )

        for region in regions:
            t = threading.Thread(target=_scan_region, args=(region,), daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        all_files: list[CarvedFile] = []
        last_end = 0

        for rr in region_results:
            if rr is None:
                continue
            self._per_thread_times.append((rr.region_id, rr.elapsed))

            for f in rr.files:
                if f.offset_start < last_end:
                    continue
                all_files.append(f)
                last_end = f.offset_end

        all_files.sort(key=lambda f: f.offset_start)
        return all_files

    def _partition(self, size: int) -> list[ScanRegion]:
        if size <= 0:
            return []

        if self.num_threads <= 1 or size < self.overlap * 2:
            return [ScanRegion(start=0, end=size, region_id=0)]

        chunk = size // self.num_threads
        if chunk < self.overlap:
            chunk = self.overlap

        regions: list[ScanRegion] = []
        for i in range(self.num_threads):
            start = i * chunk
            if start >= size:
                break

            end = min(start + chunk + self.overlap, size) if i < self.num_threads - 1 else size

            regions.append(ScanRegion(start=start, end=end, region_id=i))

        return regions

    def _scan_region_data(
        self,
        region: ScanRegion,
        progress_callback: Callable[[ScanRegion, int, int], None] | None = None,
    ) -> list[CarvedFile]:
        buffer = bytearray()
        pos = region.start
        local_results: list[CarvedFile] = []
        last_found_end = region.start

        while pos < region.end:
            to_read = min(4 * 1024 * 1024, region.end - pos)
            chunk = self.reader.read_at(pos, to_read)
            if not chunk:
                break
            buffer.extend(chunk)
            pos += len(chunk)

            data = bytes(buffer)
            for carver in self.carvers:
                for result in carver.carve(data):
                    abs_start = region.start + result.offset_start
                    abs_end = region.start + result.offset_end

                    if abs_start < last_found_end or abs_end > region.end:
                        continue

                    local_results.append(
                        CarvedFile(
                            data=result.data,
                            offset_start=abs_start,
                            offset_end=abs_end,
                            signature_name=result.signature_name,
                            extension=result.extension,
                        )
                    )
                    last_found_end = abs_end

            overlap = min(REGION_OVERLAP, len(buffer))
            if len(buffer) > overlap:
                buffer = buffer[-overlap:]

            if progress_callback is not None:
                progress_callback(region, pos, region.end)

        return local_results
