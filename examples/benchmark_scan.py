#!/usr/bin/env python3
"""Benchmark carving performance across different scanner backends.

Usage:
    python examples/benchmark_scan.py image.dd

Compares throughput, memory, and CPU for:
  - StreamingScanner (bounded memory, slower)
  - MmapScanner    (OS-cached, faster on large images)
  - ThreadedScanner (parallel carving)
"""

import argparse
import sys
from pathlib import Path

from recoverx.core.benchmark.profiler import Profiler
from recoverx.core.carving.bmp import BMPCarver
from recoverx.core.carving.gif import GIFCarver
from recoverx.core.carving.jpg import JPEGCarver
from recoverx.core.carving.pdf import PDFCarver
from recoverx.core.carving.png import PNGCarver
from recoverx.core.carving.streaming import StreamingScanner
from recoverx.core.scanner.mmap_scanner import MmapScanner
from recoverx.core.scanner.threaded_scanner import ThreadedScanner
from recoverx.core.utils.raw_reader import RawReader

CARVERS = [JPEGCarver(), PNGCarver(), GIFCarver(), BMPCarver(), PDFCarver()]


def benchmark(image_path: str) -> None:
    image = Path(image_path)
    if not image.exists():
        print(f"Error: {image_path} not found.", file=sys.stderr)
        sys.exit(1)

    size = image.stat().st_size
    print(f"Benchmarking on {image.name} ({size / 1024 / 1024:.1f} MB)\n")

    backends: list[tuple[str, dict]] = [
        ("Streaming (4 MB chunks)", {"chunk_size": 4 * 1024 * 1024}),
        ("Streaming (16 MB chunks)", {"chunk_size": 16 * 1024 * 1024}),
        ("mmap (256 MB windows)", {}),
        ("Threaded (4 workers)", {"num_threads": 4}),
    ]

    for label, kwargs in backends:
        with RawReader(str(image)) as reader:
            with Profiler(label, bytes_estimate=size) as prof:
                if label.startswith("mmap"):
                    scanner = MmapScanner(reader, CARVERS)
                elif label.startswith("Threaded"):
                    scanner = ThreadedScanner(reader, CARVERS, **kwargs)
                else:
                    scanner = StreamingScanner(reader, CARVERS, **kwargs)

                files = scanner.scan()

        m = prof.result.metrics[0]
        print(f"  {label}:")
        print(f"    Duration: {m.duration_s:.2f}s")
        print(f"    Throughput: {m.throughput_mbps:.1f} MB/s")
        print(f"    Peak RSS: {m.peak_rss_mb:.1f} MB")
        print(f"    Files found: {len(files)}")

    print("\nTip: larger chunk sizes improve throughput but increase memory.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark carving backends")
    parser.add_argument("image", help="Path to disk image")
    args = parser.parse_args()
    benchmark(args.image)
