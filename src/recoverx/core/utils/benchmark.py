"""Benchmarking utilities for scan performance measurement."""

from __future__ import annotations

import time


class ScanBenchmark:
    """Tracks scan duration, throughput, and resource usage.

    Usage::

        bench = ScanBenchmark()
        bench.start()
        ...  # perform scan
        bench.bytes_scanned = reader.size
        bench.files_found = len(results)
        bench.stop()
        print(bench.summary())
    """

    def __init__(self) -> None:
        self.start_time: float | None = None
        self.end_time: float | None = None
        self.bytes_scanned: int = 0
        self.files_found: int = 0

    def start(self) -> None:
        self.start_time = time.perf_counter()

    def stop(self) -> None:
        self.end_time = time.perf_counter()

    @property
    def elapsed(self) -> float:
        end = self.end_time if self.end_time is not None else time.perf_counter()
        start = self.start_time if self.start_time is not None else end
        return end - start

    @property
    def speed_mbps(self) -> float:
        if self.elapsed <= 0:
            return 0.0
        return (self.bytes_scanned / 1024 / 1024) / self.elapsed

    def report(self) -> dict:
        return {
            "elapsed_seconds": round(self.elapsed, 2),
            "speed_mbps": round(self.speed_mbps, 2),
            "bytes_scanned": self.bytes_scanned,
            "files_found": self.files_found,
        }

    def summary(self) -> str:
        r = self.report()
        return (
            f"[bold]Scan completed[/bold] in {r['elapsed_seconds']}s  |  "
            f"Speed: [green]{r['speed_mbps']} MB/s[/green]  |  "
            f"Files recovered: [cyan]{r['files_found']}[/cyan]"
        )
