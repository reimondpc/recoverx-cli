#!/usr/bin/env python3
"""Carve all JPEG files from a disk image using RecoverX's carving API.

Usage:
    python examples/recover_deleted_jpgs.py image.dd [--output recovered]

This example demonstrates low-level use of RawReader, JPEGCarver,
StreamingScanner, and RecoveryManager without going through the CLI.
"""

import argparse
import sys
from pathlib import Path

from recoverx.core.carving.jpg import JPEGCarver
from recoverx.core.carving.streaming import StreamingScanner
from recoverx.core.recovery.manager import RecoveryManager
from recoverx.core.utils.raw_reader import RawReader


def carve_jpegs(image_path: str, output_dir: str = "recovered") -> int:
    image = Path(image_path)
    if not image.exists():
        print(f"Error: {image_path} not found.", file=sys.stderr)
        return 1

    carvers = [JPEGCarver()]
    recovery = RecoveryManager(output_dir=output_dir)

    with RawReader(str(image)) as reader:
        print(f"Scanning {image.name} ({reader.size / 1024 / 1024:.1f} MB) ...")
        scanner = StreamingScanner(reader, carvers)
        files = scanner.scan()

    if not files:
        print("No JPEG files found.")
        return 0

    for cf in files:
        path = recovery.save(cf)
        print(
            f"  [+] {cf.signature_name} at 0x{cf.offset_start:x} "
            f"({len(cf.data)} bytes) -> {path}"
        )

    print(f"\nDone: {recovery.total_files} file(s) saved to {output_dir}/")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Carve JPEGs from a disk image")
    parser.add_argument("image", help="Path to disk image (.img, .dd, .raw)")
    parser.add_argument(
        "--output", "-o", default="recovered", help="Output directory (default: recovered)"
    )
    args = parser.parse_args()
    sys.exit(carve_jpegs(args.image, args.output))
