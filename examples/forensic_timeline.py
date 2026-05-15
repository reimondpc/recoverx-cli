#!/usr/bin/env python3
"""Build and query a forensic timeline from an NTFS disk image.

Usage:
    python examples/forensic_timeline.py image.dd

Demonstrates Timeline construction, filtering by event type,
identifying deleted files, and printing a chronological report.
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

from recoverx.core.forensics.models import EventType
from recoverx.core.forensics.timeline import Timeline
from recoverx.core.utils.raw_reader import RawReader


def analyze_timeline(image_path: str) -> None:
    image = Path(image_path)
    if not image.exists():
        print(f"Error: {image_path} not found.", file=sys.stderr)
        sys.exit(1)

    with RawReader(str(image)) as reader:
        sector0 = reader.read_at(0, 512)
        from recoverx.core.filesystems.ntfs.boot_sector import parse_boot_sector

        bpb = parse_boot_sector(sector0)
        if bpb is None:
            print("Error: Not a valid NTFS boot sector.", file=sys.stderr)
            sys.exit(1)

        from recoverx.cli.commands.sources import (
            collect_mft_events,
            collect_usn_events,
        )

        tl = Timeline()
        tl.add_events(collect_mft_events(reader, bpb))
        tl.add_events(collect_usn_events(reader, bpb))

        events = tl.events
        meta = tl.metadata

        print(f"Timeline: {len(events)} events")
        print(f"  Sources:     {meta.source_counts}")
        print(f"  Time range:  {meta.time_range_start} -- {meta.time_range_end}")
        print(f"  Unique files:{meta.unique_files}\n")

        # Deleted files
        deleted = [e for e in events if e.event_type == EventType.FILE_DELETED]
        print(f"Deleted files ({len(deleted)}):")
        for e in deleted[:15]:
            ts = e.timestamp.strftime("%Y-%m-%d %H:%M:%S") if e.timestamp else "?"
            print(f"  {ts}  MFT#{e.mft_reference}  {e.filename}")
        if len(deleted) > 15:
            print(f"  ... and {len(deleted) - 15} more")

        # Recent activity (last 7 days)
        week_ago = datetime.now() - timedelta(days=7)
        recent = [e for e in events if e.timestamp and e.timestamp >= week_ago]
        if recent:
            print(f"\nRecent activity (last 7d): {len(recent)} events")
            for e in recent[:10]:
                ts = e.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                print(f"  {ts}  {e.event_type.value}  {e.filename}")

        # File with most events
        from collections import Counter

        filename_counts = Counter(e.filename for e in events if e.filename)
        if filename_counts:
            top_file, top_count = filename_counts.most_common(1)[0]
            print(f"\nMost active file: {top_file} ({top_count} events)")
            tl.filter_by_file(top_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Forensic timeline analysis")
    parser.add_argument("image", help="Path to NTFS disk image")
    args = parser.parse_args()
    analyze_timeline(args.image)
