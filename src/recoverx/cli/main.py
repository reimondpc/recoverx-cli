#!/usr/bin/env python3

import typer
from rich.console import Console

from recoverx.cli.commands import devices as devices_cmd
from recoverx.cli.commands import info as info_cmd
from recoverx.cli.commands import scan as scan_cmd
from recoverx.cli.commands.cases import case_app
from recoverx.cli.commands.fat32 import fat32_app
from recoverx.cli.commands.forensic import forensic_app
from recoverx.cli.commands.ntfs import ntfs_app
from recoverx.cli.commands.plugins import plugins_app
from recoverx.core.utils.logger import setup_logger

app = typer.Typer(
    name="recoverx",
    help="Professional file recovery and carving tool for disk images and block devices.",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

console = Console()


@app.command()
def info() -> None:
    """Display information about connected disks and partitions."""
    info_cmd.run(console)


@app.command()
def devices(
    detailed: bool = typer.Option(
        False, "--detailed", "-d", help="Show detailed probe information for each device."
    ),
) -> None:
    """List all connected disks and raw block devices."""
    devices_cmd.run(console, detailed=detailed)


@app.command()
def scan(
    path: str = typer.Argument(
        ...,
        help="Path to a disk image (.img, .dd, .raw) or block device (/dev/sdX).",
    ),
    threads: int = typer.Option(
        0,
        "--threads",
        "-t",
        help="Number of scanner threads (0 = auto, 1 = single-threaded).",
    ),
    report: str = typer.Option(
        "",
        "--report",
        "-r",
        help="Path to write JSON forensic report.",
    ),
    no_mmap: bool = typer.Option(
        False,
        "--no-mmap",
        help="Disable memory-mapped I/O, force streaming mode.",
    ),
    chunk_size_mb: int = typer.Option(
        4,
        "--chunk-size",
        "-c",
        help="Scanner chunk size in MB.",
    ),
) -> None:
    """Scan a disk image or device for recoverable files using signature-based carving."""
    scan_cmd.run(
        console, path, threads=threads, report=report, no_mmap=no_mmap, chunk_size_mb=chunk_size_mb
    )


app.add_typer(fat32_app)
app.add_typer(ntfs_app)
app.add_typer(forensic_app)
app.add_typer(plugins_app)
app.add_typer(case_app)


def main() -> None:
    setup_logger()
    app()


if __name__ == "__main__":
    main()
