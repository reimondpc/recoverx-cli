from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime

import typer
from rich.console import Console
from rich.table import Table

from recoverx.core.forensics.reporting import (
    events_to_csv,
    events_to_json,
    events_to_markdown,
    investigation_summary,
)
from recoverx.core.forensics.timeline import Timeline
from recoverx.core.indexing.engine import IndexEngine
from recoverx.core.indexing.models import IndexConfig
from recoverx.core.query.engine import QueryEngine
from recoverx.core.utils.raw_reader import RawReader

from .sources import collect_mft_events, collect_usn_events

logger = logging.getLogger("recoverx")

forensic_app = typer.Typer(
    name="forensic",
    help="Forensic timeline analysis, indexing, querying, and investigation.",
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
        from recoverx.core.filesystems.ntfs.boot_sector import parse_boot_sector

        bpb = parse_boot_sector(sector0)
        if bpb is None:
            console.print("[red]Error:[/red] Not a valid NTFS boot sector.")
            raise typer.Exit(code=1)

        tl = Timeline()
        mft_events = collect_mft_events(reader, bpb)
        tl.add_events(mft_events)
        console.print(f"[dim]  MFT events: {len(mft_events)}[/dim]")

        usn_events = collect_usn_events(reader, bpb)
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
        console.print(f"  Time range:  {meta.time_range_start} \u2014 {meta.time_range_end}")
        console.print(f"  Unique files:{meta.unique_files}")

        if fmt == "csv" or (output and output.endswith(".csv")):
            csv_out = events_to_csv(events)
            if output:
                with open(output, "w") as f:
                    f.write(csv_out)
                console.print(f"\n[green]CSV saved:[/green] {output}")
        elif json_output or fmt == "json" or output:
            data = {"metadata": meta.to_dict(), "events": [e.to_dict() for e in events]}
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


@forensic_app.command()
def search(
    path: str = typer.Argument(..., help="Path to disk image."),
    name: str = typer.Option("", "--name", "-n", help="Filename filter."),
    event: str = typer.Option("", "--event", "-e", help="Event type filter."),
    source: str = typer.Option("", "--source", "-s", help="Event source filter."),
    sha256_hash: str = typer.Option("", "--hash", help="SHA-256 hash filter."),
    mft_ref: int = typer.Option(0, "--mft", help="MFT reference number."),
    deleted_only: bool = typer.Option(False, "--deleted-only", help="Deleted files only."),
    modified_only: bool = typer.Option(False, "--modified-only", help="Modified files only."),
    since: str = typer.Option("", "--since", help="Start timestamp."),
    until: str = typer.Option("", "--until", help="End timestamp."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
    csv_output: bool = typer.Option(False, "--csv", help="Output as CSV."),
    limit: int = typer.Option(100, "--limit", "-n", help="Max results."),
    sort: str = typer.Option("timestamp", "--sort", help="Sort field."),
    index_db: str = typer.Option("", "--index-db", help="Reuse existing index DB."),
) -> None:
    """Search indexed forensic data for files and events matching criteria."""
    console = Console()
    db_path = index_db or _default_index_path(path)
    config = IndexConfig(db_path=db_path, read_only=False)

    with IndexEngine(config) as engine:
        if not index_db:
            console.print("[dim]Indexing forensic data...[/dim]")
            _index_disk_image(engine, path, console)

        results: list[dict] = []
        if event or source or since or until or mft_ref or deleted_only:
            results = engine.search_events(
                event_type=event if event else None,
                source=source if source else None,
                filename=name if name else None,
                since=since if since else None,
                until=until if until else None,
                mft_ref=mft_ref if mft_ref else 0,
                deleted_only=deleted_only,
                limit=limit,
                sort_by=sort,
            )
        elif sha256_hash:
            dup = engine.get_duplicates(sha256_hash)
            if dup:
                results = [dict(dup)]
            if name:
                results = engine.search_files(filename=name, sha256=sha256_hash, limit=limit)
        elif name:
            results = engine.search_files(filename=name, deleted_only=deleted_only, limit=limit)
        else:
            results = engine.search_events(limit=limit)

        if not results:
            console.print("[yellow]No results found.[/yellow]")
            raise typer.Exit()

        if json_output:
            console.print(json.dumps(results, indent=2, default=str))
        elif csv_output:
            if results:
                headers = list(results[0].keys())
                console.print(",".join(headers))
                for r in results:
                    console.print(",".join(str(r.get(h, "")) for h in headers))
        else:
            table = Table(title=f"Search Results ({len(results)})")
            if results:
                for key in list(results[0].keys())[:8]:
                    table.add_column(key, style="cyan")
                for r in results:
                    row = [str(r.get(k, ""))[:40] for k in list(r.keys())[:8]]
                    table.add_row(*row)
            console.print(table)

        st = engine.stats()
        console.print(
            f"\n[dim]Index: {st.total_events} events, {st.total_files} files, "
            f"{_fmt_size(st.db_size_bytes)}[/dim]"
        )


@forensic_app.command()
def query(
    path: str = typer.Argument(..., help="Path to disk image."),
    query_string: str = typer.Argument(..., help="Forensic query string."),
    limit: int = typer.Option(100, "--limit", "-n", help="Max results."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
    explain: bool = typer.Option(False, "--explain", help="Show query plan."),
) -> None:
    """Run a forensic query against indexed data."""
    console = Console()
    db_path = _default_index_path(path)
    config = IndexConfig(db_path=db_path, read_only=False)

    with IndexEngine(config) as engine:
        _index_disk_image(engine, path, console)
        qe = QueryEngine(engine)

        if explain:
            plan = qe.explain(query_string)
            console.print(json.dumps(plan, indent=2))
            return

        try:
            results = qe.query(query_string, limit=limit)
        except ValueError as e:
            console.print(f"[red]Query error:[/red] {e}")
            raise typer.Exit(code=1)

        if not results:
            console.print("[yellow]No results.[/yellow]")
            return

        if json_output:
            console.print(json.dumps(results, indent=2, default=str))
        else:
            table = Table(title=f"Query: {query_string} ({len(results)} results)")
            for key in list(results[0].keys())[:7]:
                table.add_column(key, style="cyan")
            for r in results:
                row = [str(r.get(k, ""))[:40] for k in list(r.keys())[:7]]
                table.add_row(*row)
            console.print(table)


@forensic_app.command()
def export(
    path: str = typer.Argument(..., help="Path to disk image."),
    format: str = typer.Option("json", "--format", "-f", help="json, csv, or markdown."),
    output: str = typer.Option("", "--output", "-o", help="Output file."),
    event_filter: str = typer.Option("", "--event", "-e", help="Filter by event type."),
    since: str = typer.Option("", "--since", help="Start timestamp."),
    until: str = typer.Option("", "--until", help="End timestamp."),
) -> None:
    """Export forensic timeline in JSON, CSV, or Markdown format."""
    console = Console()
    with RawReader(path) as reader:
        sector0 = reader.read_at(0, 512)
        from recoverx.core.filesystems.ntfs.boot_sector import parse_boot_sector

        bpb = parse_boot_sector(sector0)
        if bpb is None:
            console.print("[red]Error:[/red] Not a valid NTFS boot sector.")
            raise typer.Exit(code=1)

        tl = Timeline()
        tl.add_events(collect_mft_events(reader, bpb))
        tl.add_events(collect_usn_events(reader, bpb))
        events = tl.events

        if event_filter:
            events = [e for e in events if e.event_type.value == event_filter]
        if since:
            try:
                sd = datetime.fromisoformat(since)
                events = [e for e in events if e.timestamp and e.timestamp >= sd]
            except ValueError:
                pass
        if until:
            try:
                ud = datetime.fromisoformat(until)
                events = [e for e in events if e.timestamp and e.timestamp <= ud]
            except ValueError:
                pass

        if format == "csv":
            content = events_to_csv(events)
            ext = ".csv"
        elif format == "markdown":
            content = events_to_markdown(events)
            ext = ".md"
        else:
            content = events_to_json(events)
            ext = ".json"

        if output:
            out_path = output if output.endswith(ext) else output + ext
            with open(out_path, "w") as f:
                f.write(content)
            console.print(f"[green]Exported {len(events)} events to {out_path}[/green]")
        else:
            console.print(content)


@forensic_app.command()
def summary(
    path: str = typer.Argument(..., help="Path to disk image."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Show an investigation summary of the forensic data."""
    console = Console()
    with RawReader(path) as reader:
        sector0 = reader.read_at(0, 512)
        from recoverx.core.filesystems.ntfs.boot_sector import parse_boot_sector

        bpb = parse_boot_sector(sector0)
        if bpb is None:
            console.print("[red]Error:[/red] Not a valid NTFS boot sector.")
            raise typer.Exit(code=1)

        tl = Timeline()
        tl.add_events(collect_mft_events(reader, bpb))
        tl.add_events(collect_usn_events(reader, bpb))

        s = investigation_summary(tl.events)
        if json_output:
            console.print(json.dumps(s, indent=2, default=str))
        else:
            console.print("\n[bold cyan]Investigation Summary[/bold cyan]")
            console.print(f"  Total events:     {s['total_events']}")
            console.print(f"  Unique files:     {s['unique_files']}")
            console.print(f"  Created:          {s['created_count']}")
            console.print(f"  Deleted:          {s['deleted_count']}")
            console.print(f"  Renamed:          {s['renamed_count']}")
            console.print(
                f"  Time range:       {s['time_range_start']} \u2014 {s['time_range_end']}"
            )
            if s.get("deleted_files"):
                console.print("\n  [red]Deleted files:[/red]")
                for f in s["deleted_files"][:20]:
                    console.print(f"    - {f}")
            if s.get("rename_chains"):
                console.print("\n  [yellow]Rename chains:[/yellow]")
                for ch in s["rename_chains"][:10]:
                    names = [e["from"] for e in ch["events"]] + [ch["events"][-1]["to"]]
                    console.print(f"    MFT {ch['mft_reference']}: {' -> '.join(names)}")


@forensic_app.command()
def index(
    path: str = typer.Argument(..., help="Path to disk image."),
    output: str = typer.Option("", "--output", "-o", help="Index DB path."),
    force: bool = typer.Option(False, "--force", "-f", help="Re-index if DB exists."),
) -> None:
    """Index forensic data from a disk image into SQLite."""
    console = Console()
    db_path = output or _default_index_path(path)

    if os.path.exists(db_path) and not force:
        config = IndexConfig(db_path=db_path, read_only=True)
        with IndexEngine(config) as engine:
            st = engine.stats()
            console.print(
                f"[green]Index exists:[/green] {st.total_events} events, "
                f"{st.total_files} files, {_fmt_size(st.db_size_bytes)}"
            )
            console.print("  Use --force to re-index.")
            return

    config = IndexConfig(db_path=db_path, read_only=False)
    with IndexEngine(config) as engine:
        _index_disk_image(engine, path, console)
        st = engine.stats()
        console.print(
            f"\n[green]Indexed:[/green] {st.total_events} events, {st.total_files} files, "
            f"{_fmt_size(st.db_size_bytes)}"
        )


@forensic_app.command(name="index-stats")
def index_stats(
    index_db: str = typer.Argument(..., help="Path to index DB."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Show statistics for an existing forensic index."""
    console = Console()
    if not os.path.exists(index_db):
        console.print("[red]Index database not found.[/red]")
        raise typer.Exit(code=1)

    config = IndexConfig(db_path=index_db, read_only=True)
    with IndexEngine(config) as engine:
        st = engine.stats()
        integrity = engine.integrity_check()

        if json_output:
            console.print(
                json.dumps({**st.to_dict(), "integrity": integrity}, indent=2, default=str)
            )
        else:
            console.print("\n[bold cyan]Index Statistics[/bold cyan]")
            console.print(f"  Database:         {index_db}")
            console.print(f"  Size:             {_fmt_size(st.db_size_bytes)}")
            console.print(f"  Schema version:   {st.schema_version}")
            console.print(f"  Events:           {st.total_events}")
            console.print(f"  Artifacts:        {st.total_artifacts}")
            console.print(f"  Files:            {st.total_files}")
            console.print(f"  Hashes:           {st.total_hashes}")
            console.print(f"  Correlations:     {st.total_correlations}")
            console.print(f"  Integrity:        {integrity.get('integrity_check', '?')}")
            console.print(f"  Indexed sources:  {', '.join(st.indexed_sources) or 'none'}")


@forensic_app.command()
def findings(
    path: str = typer.Argument(..., help="Path to disk image."),
    severity: str = typer.Option(
        "", "--severity", "-s", help="Minimum severity: INFO, LOW, MEDIUM, HIGH, CRITICAL."
    ),
    limit: int = typer.Option(50, "--limit", "-n", help="Max findings."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Run all analyzers and produce forensic findings."""
    console = Console()
    from recoverx.core.analyzers import (
        DuplicateActivityAnalyzer,
        MassDeleteAnalyzer,
        OrphanArtifactAnalyzer,
        SuspiciousRenameAnalyzer,
        TimestampAnomalyAnalyzer,
    )
    from recoverx.core.findings import FindingsEngine
    from recoverx.core.forensics.timeline import Timeline
    from recoverx.core.utils.raw_reader import RawReader

    from .sources import collect_mft_events, collect_usn_events

    with RawReader(path) as reader:
        sector0 = reader.read_at(0, 512)
        from recoverx.core.filesystems.ntfs.boot_sector import parse_boot_sector

        bpb = parse_boot_sector(sector0)
        if bpb is None:
            console.print("[red]Error:[/red] Not a valid NTFS boot sector.")
            raise typer.Exit(code=1)

        tl = Timeline()
        tl.add_events(collect_mft_events(reader, bpb))
        tl.add_events(collect_usn_events(reader, bpb))
        events = tl.events

        engine = FindingsEngine()
        engine.register_analyzer(MassDeleteAnalyzer())
        engine.register_analyzer(SuspiciousRenameAnalyzer())
        engine.register_analyzer(TimestampAnomalyAnalyzer())
        engine.register_analyzer(DuplicateActivityAnalyzer())
        engine.register_analyzer(OrphanArtifactAnalyzer())
        results = engine.analyze(events)

        if severity:
            sev_map = {
                "INFO": 0.1,
                "LOW": 0.3,
                "MEDIUM": 0.5,
                "HIGH": 0.7,
                "CRITICAL": 0.9,
            }
            min_score = sev_map.get(severity.upper(), 0.0)
            results = [f for f in results if f.severity.score() >= min_score]
        if limit > 0:
            results = results[:limit]

        if json_output:
            console.print(json.dumps([r.to_dict() for r in results], indent=2, default=str))
        else:
            if not results:
                console.print("[yellow]No findings.[/yellow]")
                return
            table = Table(title=f"Forensic Findings ({len(results)})")
            table.add_column("Severity", style="bold")
            table.add_column("Confidence")
            table.add_column("Title")
            table.add_column("MFT Refs")
            for r in results:
                sev_style = {
                    "CRITICAL": "red bold",
                    "HIGH": "red",
                    "MEDIUM": "yellow",
                    "LOW": "cyan",
                    "INFO": "dim",
                }.get(r.severity.name, "")
                table.add_row(
                    f"[{sev_style}]{r.severity.name}[/{sev_style}]",
                    f"{r.confidence:.2f}",
                    r.title[:60],
                    ", ".join(str(m) for m in r.mft_references[:5]),
                )
            console.print(table)

        engine.clear()


@forensic_app.command()
def graph(
    path: str = typer.Argument(..., help="Path to disk image."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
    max_nodes: int = typer.Option(100, "--max-nodes", help="Max graph nodes."),
) -> None:
    """Build a correlation graph from forensic events."""
    console = Console()
    from recoverx.core.correlation import CorrelationEngineV2
    from recoverx.core.forensics.timeline import Timeline
    from recoverx.core.utils.raw_reader import RawReader

    from .sources import collect_mft_events, collect_usn_events

    with RawReader(path) as reader:
        sector0 = reader.read_at(0, 512)
        from recoverx.core.filesystems.ntfs.boot_sector import parse_boot_sector

        bpb = parse_boot_sector(sector0)
        if bpb is None:
            console.print("[red]Error:[/red] Not a valid NTFS boot sector.")
            raise typer.Exit(code=1)

        tl = Timeline()
        tl.add_events(collect_mft_events(reader, bpb))
        tl.add_events(collect_usn_events(reader, bpb))

        engine = CorrelationEngineV2()
        result = engine.analyze(tl.events[:2000])

        g = result.get("graph", {})
        nodes = g.get("nodes", [])[:max_nodes]
        edges = g.get("edges", [])[: max_nodes * 2]

        if json_output:
            console.print(json.dumps(g, indent=2, default=str))
        else:
            console.print("\n[bold cyan]Correlation Graph:[/bold cyan]")
            console.print(f"  Total nodes: {len(nodes)} ({g.get('nodes', [])})")
            console.print(f"  Total edges: {len(edges)}")
            console.print(f"  Rename chains: {result['summary']['rename_chains']}")
            console.print(f"  Delete/recreate: {result['summary']['delete_recreate_chains']}")
            console.print(f"  Anomalies: {result['summary']['anomalies']}")
            console.print(f"  Findings: {result['summary']['heuristic_findings']}")
            console.print(f"  Critical: {result['summary']['critical_findings']}")
            console.print(f"  High: {result['summary']['high_findings']}")

            if result.get("rename_chains"):
                console.print("\n[bold]Rename Chains:[/bold]")
                for rc in result["rename_chains"][:10]:
                    names = " -> ".join(rc["filenames"])
                    console.print(f"  MFT {rc['mft_reference']}: {names}")

            if result.get("anomalies"):
                console.print("\n[bold]Anomalies:[/bold]")
                for a in result["anomalies"][:10]:
                    console.print(
                        f"  [{a['type']}] {a['description']} " f"(severity: {a['severity']})"
                    )

            if result.get("scores"):
                console.print("\n[bold]Scores:[/bold]")
                for s in result["scores"][:10]:
                    console.print(
                        f"  MFT {s['mft_reference']}: {s['filename']} "
                        f"({s['severity']}, total: {s['total_score']:.3f})"
                    )


def _default_index_path(image_path: str) -> str:
    base = os.path.splitext(os.path.basename(image_path))[0]
    return os.path.join(tempfile.gettempdir(), f"{base}_forensic.db")


def _index_disk_image(engine: IndexEngine, path: str, console: Console) -> None:
    from recoverx.core.filesystems.ntfs.boot_sector import parse_boot_sector

    try:
        with RawReader(path) as reader:
            sector0 = reader.read_at(0, 512)
            bpb = parse_boot_sector(sector0)
            if bpb is None:
                console.print("[red]Error:[/red] Not a valid NTFS boot sector.")
                return

            mft_events = collect_mft_events(reader, bpb)
            if mft_events:
                engine.index_events(mft_events, case_id="default")
                console.print(f"[dim]  Indexed {len(mft_events)} MFT events[/dim]")

            usn_events = collect_usn_events(reader, bpb)
            if usn_events:
                engine.index_events(usn_events, case_id="default")
                console.print(f"[dim]  Indexed {len(usn_events)} USN events[/dim]")

            stats = engine.stats()
            console.print(f"[dim]  DB size: {_fmt_size(stats.db_size_bytes)}[/dim]")
    except Exception as e:
        console.print(f"[red]Indexing failed:[/red] {e}")
        raise


def _fmt_size(size: int | float) -> str:
    val: float = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if val < 1024:
            return f"{val:.1f}{unit}"
        val /= 1024
    return f"{val:.1f}TB"
