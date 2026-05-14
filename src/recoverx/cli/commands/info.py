"""Disk information command.

Displays a formatted table of all detected disks, partitions, and
block devices using Rich.
"""

from rich.console import Console
from rich.table import Table

from recoverx.core.disk.detector import get_disks
from recoverx.core.utils.file_utils import format_size


def run(console: Console) -> None:
    """Query and display all connected disks and partitions."""
    disks = get_disks()

    if not disks:
        console.print("[yellow]No disks detected.[/yellow]")
        return

    table = Table(title="Connected Disks", border_style="blue")
    table.add_column("Device", style="cyan", no_wrap=True)
    table.add_column("Mount Point", style="green")
    table.add_column("Type", style="yellow")
    table.add_column("Size", justify="right", style="white")
    table.add_column("Used", justify="right", style="dim")
    table.add_column("Free", justify="right", style="dim")

    for disk in disks:
        table.add_row(
            disk["device"],
            disk["mountpoint"],
            disk["fstype"],
            format_size(disk["total"]),
            format_size(disk["used"]),
            format_size(disk["free"]),
        )

    console.print(table)
