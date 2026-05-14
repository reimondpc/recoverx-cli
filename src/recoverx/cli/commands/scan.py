"""Scan command for file carving.

Opens a disk image or block device, streams it through the chunked
streaming scanner with all registered carvers, and saves any recovered
files to the recovered/ directory.
"""

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

from recoverx.core.carving.jpg import JPEGCarver
from recoverx.core.carving.png import PNGCarver
from recoverx.core.carving.streaming import StreamingScanner
from recoverx.core.recovery.manager import RecoveryManager
from recoverx.core.utils.benchmark import ScanBenchmark
from recoverx.core.utils.file_utils import format_size
from recoverx.core.utils.hashing import HashManager
from recoverx.core.utils.raw_reader import RawReader

logger = logging.getLogger("recoverx")

CHUNK_SIZE = 4 * 1024 * 1024

# All active carvers — add new carvers here to register them in the pipeline
CARVERS = [JPEGCarver(), PNGCarver()]


def run(console: Console, path: str) -> None:
    """Scan a disk image or device for recoverable files."""
    path_obj = Path(path)

    if not path_obj.exists():
        console.print(f"[red]Error:[/red] File not found: {path}")
        raise typer.Exit(code=1)

    if not path_obj.is_file() and not path_obj.is_block_device():
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

        scanner = StreamingScanner(reader, CARVERS, chunk_size=CHUNK_SIZE)
        bench = ScanBenchmark()
        bench.bytes_scanned = file_size
        bench.start()

        carved_files: list = []
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Scanning...[/cyan]", total=file_size)

            def _progress(pos: int, total: int) -> None:
                progress.update(task, completed=pos)

            carved_files = scanner.scan(progress_callback=_progress)

        bench.stop()
        bench.files_found = len(carved_files)

        console.print()

        if not carved_files:
            console.print("[yellow]No recoverable files found.[/yellow]")
            logger.info("No recoverable files found in %s", path)
            return

        logger.info("Carving complete: %d files found", len(carved_files))

        recovery = RecoveryManager()
        hasher = HashManager()
        results_table = Table(title="Recovered Files", border_style="green")
        results_table.add_column("#", style="dim")
        results_table.add_column("File", style="cyan")
        results_table.add_column("Size", justify="right", style="green")
        results_table.add_column("SHA256", style="dim")

        for i, cf in enumerate(carved_files, 1):
            saved_path = recovery.save(cf)
            digest = hasher.compute(cf.data)

            logger.info(
                "Recovered %s at offset %d -> %s [sha256=%s]",
                cf.signature_name,
                cf.offset_start,
                saved_path,
                digest,
            )
            console.print(
                f"  [green][+][/green] {cf.signature_name} found at offset "
                f"[yellow]{cf.offset_start:,}[/yellow]"
            )
            console.print(f"      Saved: [cyan]{saved_path}[/cyan]")
            console.print(f"      SHA256: [dim]{digest}[/dim]")

            results_table.add_row(
                str(i),
                saved_path.name,
                format_size(len(cf.data)),
                digest[:16] + "...",
            )

        console.print()
        console.print(results_table)
        console.print()
        console.print(bench.summary())
        console.print(
            f"[bold green]Recovery complete:[/bold green] "
            f"{recovery.total_files} file(s) saved to [cyan]recovered/[/cyan]"
        )
