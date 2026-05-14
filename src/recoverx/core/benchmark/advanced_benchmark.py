from __future__ import annotations

import os
import time
from dataclasses import dataclass, field


@dataclass
class BenchmarkResult:
    elapsed_seconds: float = 0.0
    speed_mbps: float = 0.0
    bytes_scanned: int = 0
    files_found: int = 0
    files_per_minute: float = 0.0
    cpu_percent: float = 0.0
    peak_rss_mb: float = 0.0
    num_threads: int = 1
    per_thread_seconds: list[float] = field(default_factory=list)
    used_mmap: bool = False
    scanner_type: str = "streaming"

    def to_dict(self) -> dict:
        return {
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "speed_mbps": round(self.speed_mbps, 2),
            "bytes_scanned": self.bytes_scanned,
            "files_found": self.files_found,
            "files_per_minute": round(self.files_per_minute, 2),
            "cpu_percent": round(self.cpu_percent, 1),
            "peak_rss_mb": round(self.peak_rss_mb, 1),
            "num_threads": self.num_threads,
            "per_thread_seconds": [round(t, 2) for t in self.per_thread_seconds],
            "used_mmap": self.used_mmap,
            "scanner_type": self.scanner_type,
        }

    def summary(self) -> str:
        lines = [
            f"[bold]Scan completed[/bold] in {self.elapsed_seconds:.2f}s",
            f"  Speed:     [green]{self.speed_mbps:.1f} MB/s[/green]",
            f"  Scanned:   {self._format_bytes(self.bytes_scanned)}",
            f"  Files:     [cyan]{self.files_found}[/cyan] ({self.files_per_minute:.1f}/min)",
        ]
        if self.num_threads > 1:
            lines.append(f"  Threads:   {self.num_threads}")
        if self.used_mmap:
            lines.append("  Scanner:   mmap")
        lines.append(f"  CPU:       {self.cpu_percent:.1f}%")
        lines.append(f"  RAM peak:  {self.peak_rss_mb:.1f} MB".format(self=self))
        return "\n".join(lines)

    @staticmethod
    def _format_bytes(b: int) -> str:
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if b < 1024:
                return f"{b:.1f} {unit}"
            b /= 1024
        return f"{b:.1f} PB"


class AdvancedBenchmark:
    def __init__(self) -> None:
        self.start_time: float | None = None
        self.end_time: float | None = None
        self.bytes_scanned: int = 0
        self.files_found: int = 0
        self.num_threads: int = 1
        self.per_thread_times: list[float] = []
        self.used_mmap: bool = False
        self.scanner_type: str = "streaming"
        self._process = self._get_process()
        self._cpu_start: float = 0.0
        self._rss_peak: float = 0.0

    @staticmethod
    def _get_process():
        try:
            import psutil

            return psutil.Process(os.getpid())
        except (ImportError, AttributeError):
            return None

    def start(self) -> None:
        self.start_time = time.perf_counter()
        if self._process is not None:
            try:
                self._cpu_start = self._process.cpu_percent()
                self._rss_peak = self._process.memory_info().rss / (1024 * 1024)
            except (OSError, AttributeError):
                pass

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

    @property
    def files_per_minute(self) -> float:
        if self.elapsed <= 0:
            return 0.0
        return self.files_found / (self.elapsed / 60)

    def _get_cpu(self) -> float:
        if self._process is not None:
            try:
                return self._process.cpu_percent()
            except (OSError, AttributeError):
                pass
        return 0.0

    def _get_rss(self) -> float:
        if self._process is not None:
            try:
                rss = self._process.memory_info().rss / (1024 * 1024)
                self._rss_peak = max(self._rss_peak, rss)
                return self._rss_peak
            except (OSError, AttributeError):
                pass
        return 0.0

    def result(self) -> BenchmarkResult:
        cpu = self._get_cpu()
        rss = self._get_rss()
        return BenchmarkResult(
            elapsed_seconds=self.elapsed,
            speed_mbps=self.speed_mbps,
            bytes_scanned=self.bytes_scanned,
            files_found=self.files_found,
            files_per_minute=self.files_per_minute,
            cpu_percent=cpu,
            peak_rss_mb=rss,
            num_threads=self.num_threads,
            per_thread_seconds=list(self.per_thread_times),
            used_mmap=self.used_mmap,
            scanner_type=self.scanner_type,
        )
