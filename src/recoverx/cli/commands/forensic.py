from __future__ import annotations

import json
import logging
from datetime import datetime

import typer
from rich.console import Console

from recoverx.core.filesystems.ntfs.boot_sector import parse_boot_sector
from recoverx.core.filesystems.ntfs.recovery import NTFSRecovery
from recoverx.core.filesystems.ntfs.structures import NTFSBootSector
from recoverx.core.filesystems.ntfs.usn.mapping import map_usn_records
from recoverx.core.filesystems.ntfs.usn.parser import USNParser
from recoverx.core.forensics.models import (
    EventSource,
    ForensicEvent,
)
from recoverx.core.forensics.timeline import Timeline
from recoverx.core.utils.raw_reader import RawReader

logger = logging.getLogger("recoverx")

forensic_app = typer.Typer(
    name="forensic",
    help="Forensic timeline analysis and event reconstruction.",
    rich_markup_mode="rich",
)


@forensic_app.command()
def timeline(
    path: str = typer.Argument(..., help="Path to disk image."),
    output: str = typer.Option("", "--output", "-o", help="Output file (JSON or CSV)."),
    fmt: str = typer.Option("json", "--format", "-f", help="Output format: json, csv, text."),
    since: str = typer.Option("", "--since", help="Start timestamp (ISO format)."),
    until: str = typer.Option("", "--until", help="End timestamp (ISO format)."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
    limit: int = typer.Option(0, "--limit", "-n", help="Max events."),
) -> None:
    """Build a forensic timeline from NTFS sources (MFT + USN)."""
    console = Console()
    with RawReader(path) as reader:
        sector0 = reader.read_at(0, 512)
        bpb = parse_boot_sector(sector0)
        if bpb is None:
            console.print("[red]Error:[/red] Not a valid NTFS boot sector.")
            raise typer.Exit(code=1)

        tl = Timeline()

        mft_events = _collect_mft_events(reader, bpb)
        tl.add_events(mft_events)
        console.print(f"[dim]  MFT events: {len(mft_events)}[/dim]")

        usn_events = _collect_usn_events(reader, bpb)
        tl.add_events(usn_events)
        console.print(f"[dim]  USN events: {len(usn_events)}[/dim]")

        events = tl.events
        if since:
            try:
                since_dt = datetime.fromisoformat(since)
                events = [e for e in events if e.timestamp and e.timestamp >= since_dt]
            except ValueError:
                console.print(f"[yellow]Warning:[/yellow] Invalid --since format: {since}")
        if until:
            try:
                until_dt = datetime.fromisoformat(until)
                events = [e for e in events if e.timestamp and e.timestamp <= until_dt]
            except ValueError:
                console.print(f"[yellow]Warning:[/yellow] Invalid --until format: {until}")
        if limit > 0:
            events = events[:limit]

        meta = tl.metadata
        console.print(f"\n[bold cyan]Timeline:[/bold cyan] {len(events)} events")
        console.print(f"  Sources:     {meta.source_counts}")
        console.print(f"  Time range:  {meta.time_range_start} — {meta.time_range_end}")
        console.print(f"  Unique files:{meta.unique_files}")

        if fmt == "csv" or (output and output.endswith(".csv")):
            csv_out = Timeline().to_csv()
            for e in events:
                ...
            if output:
                with open(output, "w") as f:
                    f.write(csv_out)
                console.print(f"\n[green]CSV saved:[/green] {output}")
        elif json_output or fmt == "json" or output:
            data = {
                "metadata": meta.to_dict(),
                "events": [e.to_dict() for e in events],
            }
            if output:
                with open(output, "w") as f:
                    json.dump(data, f, indent=2)
                console.print(f"\n[green]JSON saved:[/green] {output}")
            else:
                console.print(json.dumps(data, indent=2))
        else:
            console.print()
            for i, e in enumerate(events):
                ts = e.timestamp.strftime("%Y-%m-%d %H:%M:%S") if e.timestamp else "(no ts)"
                line = f"  {ts} {e.event_type.value} {e.filename}"
                if e.previous_filename:
                    line += f" [dim](was: {e.previous_filename})[/dim]"
                line += f" [{e.source.value}]"
                console.print(line)


def _collect_mft_events(reader: RawReader, bpb: NTFSBootSector) -> list[ForensicEvent]:
    from recoverx.core.forensics.events import file_created, file_deleted, file_modified

    rec = NTFSRecovery(reader, bpb)
    records = rec.walk_mft(max_records=500)
    events: list[ForensicEvent] = []
    for r in records[:200]:
        if r.is_directory:
            continue
        si = r.standard_info
        fn = r.file_name
        fname = r.name or ""

        if si and si.created:
            events.append(
                file_created(
                    si.created,
                    fname,
                    r.header.mft_record_number,
                    fn.parent_mft if fn else 0,
                    fn.real_size if fn else 0,
                    source=EventSource.MFT,
                )
            )
        if si and si.modified and si.created != si.modified:
            events.append(
                file_modified(
                    si.modified,
                    fname,
                    r.header.mft_record_number,
                    fn.real_size if fn else 0,
                    source=EventSource.MFT,
                )
            )
        if r.is_deleted:
            events.append(
                file_deleted(
                    None,
                    fname,
                    r.header.mft_record_number,
                    fn.parent_mft if fn else 0,
                    source=EventSource.MFT,
                    notes=["MFT record marked as deleted"],
                )
            )
    return events


def _collect_usn_events(reader: RawReader, bpb: NTFSBootSector) -> list[ForensicEvent]:
    try:
        usn_parser = USNParser(reader, bpb)
        records = usn_parser.parse_raw()
        if not records:
            return []
        return map_usn_records(records)
    except (ValueError, IndexError, OSError) as e:
        logger.debug("USN collection failed: %s", e)
        return []
