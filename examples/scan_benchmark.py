#!/usr/bin/env python3
"""Benchmark scan modes: throughput, memory, and type-filtering.

Usage:
    python examples/scan_benchmark.py image.dd

Compares full scan vs quick scan with progress metrics.
"""

import sys
from pathlib import Path

from recoverx.core.benchmark.profiler import Profiler
from recoverx.core.carving.jpg import JPEGCarver
from recoverx.core.carving.png import PNGCarver
from recoverx.core.scanning.strategy import FullScanStrategy
from recoverx.core.utils.raw_reader import RawReader

CARVERS = [JPEGCarver(), PNGCarver()]


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} image.dd")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"Error: {path} not found")
        sys.exit(1)

    with RawReader(str(path)) as reader:
        size = reader.size
        print(f"Image: {path.name} ({size / 1024 / 1024:.1f} MB)\n")

        for label, strategy in [
            ("Full scan", FullScanStrategy(threads=0)),
        ]:
            with Profiler(label, bytes_estimate=size) as prof:
                files = strategy.scan(reader, CARVERS)
            m = prof.result.metrics[0]
            print(f"  {label}:")
            print(f"    Duration: {m.duration_s:.2f}s")
            print(f"    Throughput: {m.throughput_mbps:.1f} MB/s")
            print(f"    Peak RSS: {m.peak_rss_mb:.1f} MB")
            print(f"    Files: {len(files)}")


if __name__ == "__main__":
    main()
