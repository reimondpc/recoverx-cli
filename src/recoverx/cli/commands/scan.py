"""Scan command for file carving.

Opens a disk image or block device, reads it with a progress bar,
runs signature-based file carving (currently JPEG), and saves any
recovered files to the recovered/ directory.
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
from recoverx.core.recovery.manager import RecoveryManager
from recoverx.core.utils.file_utils import format_size
from recoverx.core.utils.raw_reader import RawReader

logger = logging.getLogger("recoverx")

CHUNK_SIZE = 4 * 1024 * 1024


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

        console.print("[bold]Reading image...[/bold]")
        data = bytearray()

        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Reading...[/cyan]", total=file_size)
            offset = 0
            while offset < file_size:
                chunk_size = min(CHUNK_SIZE, file_size - offset)
                chunk = reader.read_at(offset, chunk_size)
                if not chunk:
                    break
                data.extend(chunk)
                offset += len(chunk)
                progress.update(task, completed=offset)

        console.print()
        console.print("[bold]Carving files...[/bold]")

        logger.info("Starting JPEG carving on %s (%s)", path, format_size(file_size))
        carver = JPEGCarver()
        carved_files = carver.carve(bytes(data))
        logger.info("Carving complete: %d JPEG files found", len(carved_files))

        del data

        if not carved_files:
            console.print("[yellow]No recoverable JPEG files found.[/yellow]")
            logger.info("No recoverable files found in %s", path)
            return

        recovery = RecoveryManager()
        results_table = Table(title="Recovered Files", border_style="green")
        results_table.add_column("#", style="dim")
        results_table.add_column("File", style="cyan")
        results_table.add_column("Offset", justify="right", style="yellow")
        results_table.add_column("Size", justify="right", style="green")

        for i, cf in enumerate(carved_files, 1):
            saved_path = recovery.save(cf)
            logger.info(
                "Recovered %s at offset %d -> %s",
                cf.signature_name,
                cf.offset_start,
                saved_path,
            )
            console.print(
                f"  [green][+][/green] {cf.signature_name} found at offset "
                f"[yellow]{cf.offset_start:,}[/yellow]"
            )
            console.print(f"      Saved: [cyan]{saved_path}[/cyan]")
            results_table.add_row(
                str(i),
                saved_path.name,
                f"0x{cf.offset_start:X} ({cf.offset_start:,})",
                format_size(len(cf.data)),
            )

        console.print()
        console.print(results_table)
        console.print()
        console.print(
            f"[bold green]Recovery complete:[/bold green] "
            f"{recovery.total_files} file(s) saved to [cyan]recovered/[/cyan]"
        )
