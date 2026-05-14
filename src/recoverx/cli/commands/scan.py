from __future__ import annotations

import logging
from pathlib import Path

import typer
from rich.console import Console
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
from recoverx.core.carving.streaming import StreamingScanner
from recoverx.core.recovery.manager import RecoveryManager
from recoverx.core.reporting.json_report import JSONReport
from recoverx.core.utils.file_utils import format_size
from recoverx.core.utils.hash_database import HashDatabase
from recoverx.core.utils.hashing import HashManager
from recoverx.core.utils.raw_reader import RawReader

logger = logging.getLogger("recoverx")

CARVERS = [JPEGCarver(), PNGCarver(), GIFCarver(), BMPCarver(), PDFCarver()]


def run(
    console: Console,
    path: str,
    threads: int = 0,
    report: str = "",
    no_mmap: bool = False,
    chunk_size_mb: int = 4,
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

    console.print(f"[bold cyan]RecoverX[/bold cyan] — Scanning [yellow]{path}[/yellow]")

    with RawReader(str(path_obj)) as reader:
        file_size = reader.size
        console.print(f"  Size:    [green]{format_size(file_size)}[/green]")
        console.print(f"  Sectors: [green]{reader.sector_count:,}[/green]")
        console.print()

        if file_size == 0:
            console.print("[red]Error:[/red] File is empty.")
            raise typer.Exit(code=1)

        console.print("[bold]Scanning image...[/bold]")

        chunk_size = chunk_size_mb * 1024 * 1024

        if threads > 0 or threads == 0:
            import os

            auto_threads = max(1, os.cpu_count() or 4) if threads == 0 else threads
            if auto_threads > 1:
                _run_threaded(
                    console, reader, file_size, chunk_size, auto_threads, path, report, no_mmap
                )
                return

        if not no_mmap and not path.startswith("/dev/"):
            try:
                _run_mmap(console, reader, file_size, chunk_size, path, report)
                return
            except Exception as e:
                logger.debug("mmap scanner failed (%s), falling back to streaming", e)

        _run_streaming(console, reader, file_size, chunk_size, path, report)


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

    console.print(
        "  [yellow]Warning:[/yellow] Scanning raw device. This is a read-only operation."
    )


def _run_streaming(
    console: Console,
    reader: RawReader,
    file_size: int,
    chunk_size: int,
    path: str,
    report_path: str,
) -> None:
    from recoverx.core.benchmark.advanced_benchmark import AdvancedBenchmark

    scanner = StreamingScanner(reader, CARVERS, chunk_size=chunk_size)
    bench = AdvancedBenchmark()
    bench.bytes_scanned = file_size
    bench.scanner_type = "streaming"
    bench.start()

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Scanning...[/cyan]", total=file_size)

        def _cb(pos: int, total: int) -> None:
            progress.update(task, completed=pos)

        carved_files = scanner.scan(progress_callback=_cb)

    _finish_scan(console, carved_files, bench, file_size, path, report_path)


def _run_mmap(
    console: Console,
    reader: RawReader,
    file_size: int,
    chunk_size: int,
    path: str,
    report_path: str,
) -> None:
    from recoverx.core.benchmark.advanced_benchmark import AdvancedBenchmark
    from recoverx.core.scanner.mmap_scanner import MmapScanner

    scanner = MmapScanner(reader, CARVERS, chunk_size=chunk_size)
    bench = AdvancedBenchmark()
    bench.bytes_scanned = file_size
    bench.scanner_type = "mmap"
    bench.start()

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Scanning (mmap)...[/cyan]", total=file_size)

        def _cb(pos: int, total: int) -> None:
            progress.update(task, completed=pos)

        carved_files = scanner.scan(progress_callback=_cb)

    bench.used_mmap = scanner.used_mmap
    _finish_scan(console, carved_files, bench, file_size, path, report_path)


def _run_threaded(
    console: Console,
    reader: RawReader,
    file_size: int,
    chunk_size: int,
    num_threads: int,
    path: str,
    report_path: str,
    no_mmap: bool,
) -> None:
    from recoverx.core.benchmark.advanced_benchmark import AdvancedBenchmark
    from recoverx.core.scanner.threaded_scanner import ThreadedScanner

    scanner = ThreadedScanner(reader, CARVERS, num_threads=num_threads)
    bench = AdvancedBenchmark()
    bench.bytes_scanned = file_size
    bench.num_threads = num_threads
    bench.scanner_type = f"threaded_{num_threads}"
    bench.start()

    console.print(f"  Threads:  [green]{num_threads}[/green]")
    console.print()

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Scanning (threaded)...[/cyan]", total=file_size)

        def _cb(pos: int, total: int) -> None:
            progress.update(task, completed=pos)

        carved_files = scanner.scan(progress_callback=_cb)

    bench.per_thread_times = [t for _, t in scanner.per_thread_times]
    bench.stop()

    # Benchmark shows per-thread timing
    if scanner.per_thread_times:
        for rid, elapsed in scanner.per_thread_times:
            console.print(f"  Thread #{rid + 1}: [dim]{elapsed:.2f}s[/dim]")

    _finish_scan(console, carved_files, bench, file_size, path, report_path)


def _finish_scan(
    console: Console,
    carved_files: list,
    bench,
    file_size: int,
    path: str,
    report_path: str,
) -> None:
    bench.stop()
    bench.files_found = len(carved_files)
    result = bench.result()

    console.print()

    if not carved_files:
        console.print("[yellow]No recoverable files found.[/yellow]")
        logger.info("No recoverable files found in %s", path)
        _write_report(report_path, [], result, path, file_size, len(CARVERS))
        return

    logger.info("Carving complete: %d files found", len(carved_files))

    recovery = RecoveryManager()
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
            num_carvers=len(CARVERS),
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
    console.print(
        f"[bold green]Recovery complete:[/bold green] "
        f"{recovery.total_files} file(s) saved to [cyan]recovered/[/cyan]"
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
