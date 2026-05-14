"""Performance profiler for RecoverX.

Provides CPU, memory, and throughput profiling for all core operations.
Metrics are exportable to JSON for forensic performance analysis.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict

logger = logging.getLogger("recoverx")


@dataclass
class ProfileMetric:
    operation: str
    duration_s: float = 0.0
    bytes_processed: int = 0
    throughput_mbps: float = 0.0
    peak_rss_mb: float = 0.0
    items_count: int = 0
    notes: str = ""


@dataclass
class ProfileResult:
    metrics: list[ProfileMetric] = field(default_factory=list)
    total_duration_s: float = 0.0
    total_bytes: int = 0
    avg_throughput_mbps: float = 0.0

    def add_metric(self, metric: ProfileMetric) -> None:
        self.metrics.append(metric)

    def to_dict(self) -> dict:
        return {
            "total_duration_s": round(self.total_duration_s, 4),
            "total_bytes": self.total_bytes,
            "avg_throughput_mbps": round(self.avg_throughput_mbps, 2),
            "metrics": [asdict(m) for m in self.metrics],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class Profiler:
    """Context manager for profiling code blocks.

    Usage:
        with Profiler("FAT parsing") as p:
            result = parse_boot_sector(data)
        print(p.result.to_json())
    """

    def __init__(self, operation: str, bytes_estimate: int = 0):
        self.operation = operation
        self.bytes_estimate = bytes_estimate
        self.result = ProfileResult()

    def __enter__(self):
        self.start = time.perf_counter()
        self.mem_start = self._get_rss()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.perf_counter() - self.start
        mem_end = self._get_rss()
        peak = max(self.mem_start, mem_end)
        throughput = (
            (self.bytes_estimate / elapsed / 1024 / 1024)
            if elapsed > 0 and self.bytes_estimate > 0
            else 0.0
        )
        metric = ProfileMetric(
            operation=self.operation,
            duration_s=round(elapsed, 4),
            bytes_processed=self.bytes_estimate,
            throughput_mbps=round(throughput, 2),
            peak_rss_mb=round(peak, 1),
        )
        self.result.add_metric(metric)
        self.result.total_duration_s = elapsed
        self.result.total_bytes = self.bytes_estimate
        self.result.avg_throughput_mbps = throughput

    @staticmethod
    def _get_rss() -> float:
        try:
            return int(open(f"/proc/{os.getpid()}/statm").read().split()[1]) * 4096 / 1024 / 1024
        except (IOError, IndexError, ValueError):
            return 0.0


def profile_operation(operation: str, bytes_estimate: int = 0):
    """Decorator for profiling individual functions.

    Usage:
        @profile_operation("FAT chain read", bytes_estimate=4096)
        def read_chain(reader, bpb, cluster):
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            with Profiler(operation, bytes_estimate) as p:
                result = func(*args, **kwargs)
            logger.info(
                "Profile [%s]: %.4fs | %.2f MB/s | %d bytes",
                operation,
                p.result.total_duration_s,
                p.result.avg_throughput_mbps,
                bytes_estimate,
            )
            return result
        return wrapper
    return decorator
