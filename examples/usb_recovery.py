#!/usr/bin/env python3
"""Recover JPEG photos from a USB drive using quick scan mode.

Usage:
    python examples/usb_recovery.py /dev/sdb1 --output photos/

Demonstrates quick scan, type filtering, and custom output directory.
"""

import sys

from recoverx.cli.commands import scan as scan_cmd
from recoverx.cli.main import console


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} /dev/sdX [--output dir]")
        sys.exit(1)

    path = sys.argv[1]
    output = sys.argv[3] if len(sys.argv) > 3 and sys.argv[2] == "--output" else "photos"
    scan_cmd.run(
        console,
        path,
        quick=True,
        type_filter="jpg,jpeg",
        output_dir=output,
        live_findings=True,
    )


if __name__ == "__main__":
    main()
