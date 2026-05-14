#!/usr/bin/env python3
"""RecoverX — Professional file recovery and carving tool.

Entry point for the CLI application.  Registers the ``info`` and ``scan``
commands and initialises logging before dispatching to Typer.
"""

import typer
from rich.console import Console

from recoverx.cli.commands import info as info_cmd
from recoverx.cli.commands import scan as scan_cmd
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
def scan(
    path: str = typer.Argument(
        ...,
        help="Path to a disk image (.img, .dd, .raw) or block device (/dev/sdX).",
    ),
) -> None:
    """Scan a disk image or device for recoverable files using signature-based carving."""
    scan_cmd.run(console, path)


def main() -> None:
    """Application entry point.  Called by the ``recoverx`` console script."""
    setup_logger()
    app()


if __name__ == "__main__":
    main()
