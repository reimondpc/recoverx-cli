from __future__ import annotations

import logging
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.live import Live
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from recoverx.cli.commands.devices import detect_raw_devices
from recoverx.core.carving.bmp import BMPCarver
from recoverx.core.carving.gif import GIFCarver
from recoverx.core.carving.jpg import JPEGCarver
from recoverx.core.carving.pdf import PDFCarver
from recoverx.core.carving.png import PNGCarver
from recoverx.core.recovery.manager import RecoveryManager
from recoverx.core.reporting.json_report import JSONReport
from recoverx.core.scanning import InterruptHandler, ScanInterrupted
from recoverx.core.scanning.progress import ScanProgress
from recoverx.core.scanning.strategy import FullScanStrategy, QuickScanStrategy
from recoverx.core.utils.file_utils import format_size
from recoverx.core.utils.hash_database import HashDatabase
from recoverx.core.utils.hashing import HashManager
from recoverx.core.utils.raw_reader import RawReader

logger = logging.getLogger("recoverx")

ALL_CARVERS = [JPEGCarver(), PNGCarver(), GIFCarver(), BMPCarver(), PDFCarver()]
CARVER_MAP: dict[str, type] = {
    "jpg": JPEGCarver,
    "jpeg": JPEGCarver,
    "png": PNGCarver,
    "gif": GIFCarver,
    "bmp": BMPCarver,
    "pdf": PDFCarver,
}


def _resolve_carvers(type_filter: str | None) -> list:
    if not type_filter:
        return list(ALL_CARVERS)
    names = [t.strip().lower() for t in type_filter.split(",")]
    selected: list = []
    for name in names:
        cls = CARVER_MAP.get(name)
        if cls is None:
            valid = ", ".join(sorted(CARVER_MAP.keys()))
            raise typer.BadParameter(f"Unknown type '{name}'. Valid types: {valid}")
        selected.append(cls())
    return selected


def _parse_size(value: str) -> int:
    value = value.strip().upper()
    multipliers = [("TB", 1024**4), ("GB", 1024**3), ("MB", 1024**2), ("KB", 1024), ("B", 1)]
    for suffix, mult in multipliers:
        if value.endswith(suffix):
            num_part = value[: -len(suffix)]
            if not num_part:
                continue
            try:
                return int(float(num_part) * mult)
            except ValueError:
                raise typer.BadParameter(f"Invalid size: {value}")
    try:
        return int(value)
    except ValueError:
        raise typer.BadParameter(f"Invalid size: {value}")


def _parse_time(value: str) -> float:
    value = value.strip().lower()
    multipliers = {"s": 1, "m": 60, "h": 3600}
    if value and value[-1] in multipliers:
        try:
            return float(value[:-1]) * multipliers[value[-1]]
        except ValueError:
            raise typer.BadParameter(f"Invalid time: {value}")
    try:
        return float(value)
    except ValueError:
        raise typer.BadParameter(f"Invalid time: {value}")


def _validate_device(device_path: str, console: Console) -> None:
    import os

    if not os.path.exists(device_path):
        console.print(f"[red]Error:[/red] Device not found: {device_path}")
        console.print("Available devices:")
        for dev in detect_raw_devices():
            console.print(f"  {dev}")
        raise typer.Exit(code=1)

    if not os.access(device_path, os.R_OK):
        console.print(
            f"[red]Error:[/red] Permission denied: {device_path}\n"
            f"  Try running with: [yellow]sudo recoverx scan {device_path}[/yellow]"
        )
        raise typer.Exit(code=1)

    console.print("  [yellow]Warning:[/yellow] Scanning raw device. This is a read-only operation.")


def run(
    console: Console,
    path: str,
    threads: int = 0,
    report: str = "",
    no_mmap: bool = False,
    chunk_size_mb: int = 4,
    quick: bool = False,
    max_size: str = "",
    max_time: str = "",
    output_dir: str = "",
    type_filter: str | None = None,
    live_findings: bool = False,
) -> None:
    path_obj = Path(path)

    if not path_obj.exists() and not path.startswith("/dev/"):
        console.print(f"[red]Error:[/red] File not found: {path}")
        raise typer.Exit(code=1)

    if path.startswith("/dev/"):
        _validate_device(path, console)
    elif not path_obj.is_file():
        console.print("[red]Error:[/red] Path must be a regular file or block device.")
        raise typer.Exit(code=1)

    carvers = _resolve_carvers(type_filter)
    console.print(f"[bold cyan]RecoverX[/bold cyan] — Scanning [yellow]{path}[/yellow]")
    console.print(f"  Carvers:  [green]{', '.join(c.signature.name for c in carvers)}[/green]")

    max_bytes = _parse_size(max_size) if max_size else 0
    max_time_sec = _parse_time(max_time) if max_time else 0.0

    with RawReader(str(path_obj)) as reader:
        file_size = reader.size
        effective_size = min(file_size, max_bytes) if max_bytes > 0 else file_size
        console.print(f"  Size:     [green]{format_size(file_size)}[/green]")
        console.print(f"  Sectors:  [green]{reader.sector_count:,}[/green]")
        if quick:
            console.print("  Mode:     [yellow]quick scan[/yellow]")
        if max_bytes > 0:
            console.print(f"  Limit:    [yellow]{format_size(max_bytes)}[/yellow]")
        if max_time_sec > 0:
            console.print(f"  Timeout:  [yellow]{max_time_sec:.0f}s[/yellow]")
        console.print()

        if file_size == 0:
            console.print("[red]Error:[/red] File is empty.")
            raise typer.Exit(code=1)

        use_threads = max(1, __import__("os").cpu_count() or 4) if threads == 0 else threads

        handler = InterruptHandler()
        progress = ScanProgress(total_bytes=effective_size)
        if use_threads > 1:
            progress.active_threads = use_threads

        strategy: FullScanStrategy | QuickScanStrategy
        if quick:
            strategy = QuickScanStrategy()
            strategy.max_bytes = effective_size
        else:
            strategy = FullScanStrategy(
                threads=threads,
                no_mmap=no_mmap,
                chunk_size_mb=chunk_size_mb,
                max_bytes=effective_size,
                max_time=max_time_sec,
            )

        _run_with_progress(
            console,
            reader,
            carvers,
            strategy,
            progress,
            handler,
            report,
            output_dir,
            live_findings,
            max_time_sec,
        )


def _build_live_display(progress: ScanProgress, findings_preview: list[str]) -> Table:
    table = Table.grid(padding=(0, 1))
    table.add_column()
    info = progress.to_dict()

    scanned_str = format_size(info["scanned"])
    total_str = format_size(info["total"])
    pct = info["percentage"]

    bar_width = 20
    filled = int(bar_width * pct / 100)
    bar = "█" * filled + "░" * (bar_width - filled)

    table.add_row("[bold]Scanning...[/bold]")
    table.add_row(f"[cyan]{bar}[/cyan] [green]{pct:.0f}%[/green]")
    table.add_row(f"  Scanned:  {scanned_str} / {total_str}")
    table.add_row(f"  Speed:    [green]{info['throughput_mbps']:.1f} MB/s[/green]")
    if info["eta_s"] > 0:
        eta_m = int(info["eta_s"] // 60)
        eta_s = int(info["eta_s"] % 60)
        table.add_row(f"  ETA:      {eta_m}m {eta_s:02d}s")
    table.add_row(f"  Elapsed:  {info['elapsed_s']:.0f}s")
    table.add_row(f"  Threads:  {info['active_threads']}")

    findings = info["findings"]
    if findings:
        parts = [f"[yellow]{k}={v}[/yellow]" for k, v in sorted(findings.items())]
        table.add_row(f"  Found:    {', '.join(parts)}")
    else:
        table.add_row("  Found:    [dim]none yet[/dim]")

    if findings_preview:
        for line in findings_preview[-3:]:
            table.add_row(f"  [dim]{line}[/dim]")

    return table


def _run_with_progress(
    console: Console,
    reader: RawReader,
    carvers: list,
    strategy: FullScanStrategy | QuickScanStrategy,
    progress: ScanProgress,
    handler: InterruptHandler,
    report_path: str,
    output_dir: str,
    live_findings: bool,
    max_time_sec: float,
) -> None:
    from recoverx.core.benchmark.advanced_benchmark import AdvancedBenchmark

    bench = AdvancedBenchmark()
    bench.bytes_scanned = progress.total_bytes
    bench.scanner_type = "quick" if isinstance(strategy, QuickScanStrategy) else "full"
    bench.num_threads = progress.active_threads
    bench.start()

    carved_files: list = []
    findings_preview: list[str] = []
    start_time = time.monotonic()

    def _progress_cb(pos: int, total: int) -> None:
        progress.update(scanned=pos)
        if max_time_sec > 0 and (time.monotonic() - start_time) > max_time_sec:
            handler.interrupted = True

    def _interrupt_check() -> bool:
        return handler.interrupted

    bar_progress = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=True,
    )

    live_display = (
        Live(_build_live_display(progress, findings_preview), console=console, refresh_per_second=4)
        if console.is_terminal
        else None
    )

    try:
        with handler:
            task = bar_progress.add_task("[cyan]Scanning...[/cyan]", total=progress.total_bytes)

            def _rich_cb(pos: int, total: int) -> None:
                _progress_cb(pos, total)
                bar_progress.update(task, completed=pos)

            if live_display:
                live_display.start()

            carved_files = strategy.scan(
                reader,
                carvers,
                progress_callback=_rich_cb if not live_display else _progress_cb,
                interrupt_check=_interrupt_check,
            )

    except ScanInterrupted:
        pass
    finally:
        if live_display:
            live_display.stop()

        bench.stop()
        bench.files_found = len(carved_files)

    if handler.interrupted:
        console.print("\n[yellow]Scan interrupted. Partial results preserved.[/yellow]")

    _finish_scan(
        console,
        carved_files,
        bench,
        reader.size,
        getattr(reader, "path", ""),
        report_path,
        output_dir,
        handler.interrupted,
    )


def _finish_scan(
    console: Console,
    carved_files: list,
    bench,
    file_size: int,
    path: str,
    report_path: str,
    output_dir: str,
    was_interrupted: bool = False,
) -> None:
    bench.files_found = len(carved_files)
    result = bench.result()

    console.print()
    result_str = "Scan cancelled" if was_interrupted else "Scan completed"
    console.print(f"[bold]{result_str}[/bold] in {result.elapsed_seconds:.2f}s")

    if not carved_files:
        console.print("[yellow]No recoverable files found.[/yellow]")
        logger.info("No recoverable files found in %s", path)
        _write_report(report_path, [], result, path, file_size, 0)
        return

    logger.info("Carving complete: %d files found", len(carved_files))

    recovery = RecoveryManager(output_dir=output_dir)
    hasher = HashManager()
    hash_db = HashDatabase()

    report = JSONReport(report_path) if report_path else None

    results_table = Table(title="Recovered Files", border_style="green")
    results_table.add_column("#", style="dim")
    results_table.add_column("File", style="cyan")
    results_table.add_column("Offset", style="yellow")
    results_table.add_column("Size", justify="right", style="green")
    results_table.add_column("SHA256", style="dim")

    for i, cf in enumerate(carved_files, 1):
        saved_path = recovery.save(cf)
        digest = hasher.compute(cf.data)

        hash_db.add(digest, str(saved_path), len(cf.data), cf.extension)

        console.print(
            f"  [green][+][/green] {cf.signature_name} found at offset "
            f"[yellow]{cf.offset_start:,}[/yellow]"
        )
        console.print(f"      Saved: [cyan]{saved_path}[/cyan]")
        console.print(f"      SHA256: [dim]{digest}[/dim]")

        results_table.add_row(
            str(i),
            saved_path.name,
            f"0x{cf.offset_start:x} ({cf.offset_start:,})",
            format_size(len(cf.data)),
            digest[:16] + "...",
        )

        if report is not None:
            report.add_file(cf, digest, str(saved_path))

    if report is not None:
        report.set_benchmark(result)
        report.set_scan_info(
            source=path,
            source_size=file_size,
            num_carvers=len(bench.__dict__.get("num_carvers", 0)),
            num_threads=result.num_threads,
            used_mmap=result.used_mmap,
        )
        report_path_written = report.write()
        console.print(f"\n  [blue]Report:[/blue] {report_path_written}")

    console.print()
    console.print(results_table)
    console.print()

    hash_stats = hash_db.statistics()
    console.print(result.summary())
    console.print()
    saved_dir = output_dir if output_dir else "recovered/"
    console.print(
        f"[bold green]Recovery complete:[/bold green] "
        f"{recovery.total_files} file(s) saved to [cyan]{saved_dir}[/cyan]"
    )
    console.print(
        f"  [dim]Hash DB: {hash_stats['unique_files']} unique / "
        f"{hash_stats['total_occurrences']} total occurrences[/dim]"
    )


def _write_report(
    report_path: str,
    carved_files: list,
    result,
    source: str,
    source_size: int,
    num_carvers: int,
) -> None:
    if not report_path:
        return
    report = JSONReport(report_path)
    report.set_benchmark(result)
    report.set_scan_info(
        source=source,
        source_size=source_size,
        num_carvers=num_carvers,
    )
    report.write()
