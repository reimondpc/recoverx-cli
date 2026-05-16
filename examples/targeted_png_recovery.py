#!/usr/bin/env python3
"""Scan for PNG images only, with size limit.

Usage:
    python examples/targeted_png_recovery.py image.dd --max-size 1GB

Demonstrates type filtering and scan limits.
"""

import sys

from recoverx.cli.commands import scan as scan_cmd
from recoverx.cli.main import console


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} image.dd [--max-size N]")
        sys.exit(1)

    path = sys.argv[1]
    max_size = sys.argv[3] if len(sys.argv) > 3 and sys.argv[2] == "--max-size" else "0"
    scan_cmd.run(
        console,
        path,
        type_filter="png",
        max_size=max_size,
        quick=True,
    )


if __name__ == "__main__":
    main()
