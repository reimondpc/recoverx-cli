from __future__ import annotations

import threading
import time
from collections import Counter


class ScanProgress:
    """Thread-safe scan progress tracker with throughput, ETA, and findings.

    Usage:
        progress = ScanProgress(total_bytes=file_size)
        progress.update(scanned=pos)
        progress.register_finding("JPEG")
    """

    def __init__(self, total_bytes: int) -> None:
        self.total_bytes = total_bytes
        self._scanned = 0
        self._start_time = time.monotonic()
        self._findings: Counter[str] = Counter()
        self._lock = threading.Lock()
        self._active_threads = 1

    @property
    def scanned(self) -> int:
        with self._lock:
            return self._scanned

    @scanned.setter
    def scanned(self, value: int) -> None:
        with self._lock:
            self._scanned = value

    @property
    def percentage(self) -> float:
        if self.total_bytes <= 0:
            return 0.0
        with self._lock:
            return (self._scanned / self.total_bytes) * 100

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self._start_time

    @property
    def throughput_mbps(self) -> float:
        e = self.elapsed
        if e <= 0:
            return 0.0
        with self._lock:
            return (self._scanned / 1024 / 1024) / e

    @property
    def eta(self) -> float:
        e = self.elapsed
        with self._lock:
            remaining = self.total_bytes - self._scanned
        if e <= 0 or remaining <= 0:
            return 0.0
        rate = self._scanned / e
        if rate <= 0:
            return 0.0
        return remaining / rate

    @property
    def findings_counts(self) -> dict[str, int]:
        with self._lock:
            return dict(self._findings)

    @property
    def total_findings(self) -> int:
        with self._lock:
            return sum(self._findings.values())

    @property
    def active_threads(self) -> int:
        with self._lock:
            return self._active_threads

    @active_threads.setter
    def active_threads(self, value: int) -> None:
        with self._lock:
            self._active_threads = value

    def update(self, scanned: int) -> None:
        with self._lock:
            self._scanned = scanned

    def add_finding(self, signature_name: str) -> None:
        with self._lock:
            self._findings[signature_name] += 1

    def to_dict(self) -> dict:
        return {
            "scanned": self.scanned,
            "total": self.total_bytes,
            "percentage": round(self.percentage, 1),
            "elapsed_s": round(self.elapsed, 1),
            "throughput_mbps": round(self.throughput_mbps, 1),
            "eta_s": round(self.eta, 1),
            "active_threads": self.active_threads,
            "findings": self.findings_counts,
        }

    def reset_timer(self) -> None:
        self._start_time = time.monotonic()
