from __future__ import annotations

import json
import logging
from typing import List

import typer
from rich.console import Console
from rich.table import Table

from recoverx.core.filesystems.fat32.boot_sector import parse_boot_sector, validate_boot_sector
from recoverx.core.filesystems.fat32.directory import walk_directory_tree
from recoverx.core.filesystems.fat32.recovery import FAT32Recovery
from recoverx.core.filesystems.fat32.structures import FAT32BootSector
from recoverx.core.utils.file_utils import format_size
from recoverx.core.utils.raw_reader import RawReader

logger = logging.getLogger("recoverx")

fat32_app = typer.Typer(
    name="fat32",
    help="FAT32 filesystem analysis and recovery commands.",
    rich_markup_mode="rich",
)


@fat32_app.command()
def info(
    path: str = typer.Argument(..., help="Path to FAT32 disk image or device."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Display FAT32 boot sector information."""
    console = Console()

    with RawReader(path) as reader:
        sector0 = reader.read_at(0, 512)
        bpb = parse_boot_sector(sector0)

        if bpb is None:
            console.print("[red]Error:[/red] Not a valid FAT32 boot sector.")
            raise typer.Exit(code=1)

        issues = validate_boot_sector(bpb)

        if json_output:
            data = bpb.to_dict()
            data["issues"] = issues
            console.print(json.dumps(data, indent=2))
            return

        console.print("[bold cyan]FAT32 Boot Sector[/bold cyan]")
        console.print(f"  OEM ID:           [yellow]{bpb.oem_id}[/yellow]")
        console.print(f"  Bytes/Sector:     {bpb.bytes_per_sector}")
        console.print(f"  Sectors/Cluster:  {bpb.sectors_per_cluster}")
        console.print(f"  Cluster Size:     [green]{format_size(bpb.cluster_size)}[/green]")
        console.print(f"  Reserved Sectors: {bpb.reserved_sectors}")
        console.print(f"  FAT Count:        {bpb.fat_count}")
        console.print(f"  FAT Size:         {bpb.fat_size_sectors} sectors")
        console.print(f"  Root Cluster:     {bpb.root_cluster}")
        console.print(f"  Total Sectors:    {bpb.total_sectors:,}")
        console.print(f"  Total Clusters:   {bpb.total_clusters:,}")
        console.print(f"  Volume Label:     [cyan]{bpb.volume_label}[/cyan]")
        console.print(f"  Volume ID:        {bpb.volume_id}")
        sig_str = "[green]Valid[/green]" if bpb.signature_valid else "[red]Invalid[/red]"
        console.print(f"  Signature:        {sig_str}")

        console.print("\n[bold]Layout[/bold]")
        console.print(f"  FAT #1 start:     0x{bpb.fat_start:x} ({bpb.fat_start:,})")
        console.print(f"  Data region start: 0x{bpb.data_start:x} ({bpb.data_start:,})")

        if issues:
            console.print("\n[bold yellow]Issues:[/bold yellow]")
            for issue in issues:
                console.print(f"  [yellow]*[/yellow] {issue}")
        else:
            console.print("\n[green]No issues detected.[/green]")


@fat32_app.command()
def list(
    path: str = typer.Argument(..., help="Path to FAT32 disk image or device."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """List files and directories on a FAT32 volume."""
    console = Console()
    _require_bpb(console, path, lambda reader, bpb: _list_files(console, reader, bpb, json_output))


@fat32_app.command()
def deleted(
    path: str = typer.Argument(..., help="Path to FAT32 disk image or device."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """List deleted files on a FAT32 volume."""
    console = Console()
    _require_bpb(
        console, path, lambda reader, bpb: _list_deleted(console, reader, bpb, json_output)
    )


@fat32_app.command()
def recover(
    path: str = typer.Argument(..., help="Path to FAT32 disk image or device."),
    output: str = typer.Option("recovered", "--output", "-o", help="Output directory."),
    deleted_only: bool = typer.Option(True, "--deleted-only", help="Only recover deleted files."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Recover files from a FAT32 volume."""
    console = Console()
    _require_bpb(
        console,
        path,
        lambda reader, bpb: _recover_files(console, reader, bpb, output, deleted_only, json_output),
    )


def _require_bpb(console: Console, path: str, callback) -> None:
    with RawReader(path) as reader:
        sector0 = reader.read_at(0, 512)
        bpb = parse_boot_sector(sector0)
        if bpb is None:
            console.print("[red]Error:[/red] Not a valid FAT32 boot sector.")
            raise typer.Exit(code=1)
        callback(reader, bpb)


def _list_files(console: Console, reader, bpb: FAT32BootSector, json_output: bool) -> None:
    entries = walk_directory_tree(reader, bpb)

    if json_output:
        data = {"filesystem": bpb.to_dict(), "files": [e[1].to_dict() for e in entries]}
        console.print(json.dumps(data, indent=2))
        return

    console.print(f"[bold cyan]FAT32 Filesystem[/bold cyan] — [yellow]{bpb.volume_label}[/yellow]")
    console.print(f"  {len(entries)} entries found\n")

    table = Table(border_style="blue")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="yellow")
    table.add_column("Size", justify="right", style="green")
    table.add_column("Cluster", justify="right", style="white")
    table.add_column("Modified", style="dim")

    for path, entry in entries:
        ts = entry.last_modified.to_datetime()
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S") if ts else ""
        table.add_row(
            path,
            "DIR" if entry.is_directory else "FILE",
            format_size(entry.file_size) if not entry.is_directory else "",
            str(entry.start_cluster) if entry.start_cluster else "",
            ts_str,
        )

    console.print(table)


def _list_deleted(console: Console, reader, bpb: FAT32BootSector, json_output: bool) -> None:
    recovery = FAT32Recovery(reader, bpb)
    deleted_entries = recovery.find_deleted_entries()

    if json_output:
        data = {
            "filesystem": bpb.to_dict(),
            "deleted_files": [e.to_dict() for e in deleted_entries],
        }
        console.print(json.dumps(data, indent=2))
        return

    if not deleted_entries:
        console.print("[yellow]No deleted files found.[/yellow]")
        return

    console.print(
        f"[bold cyan]Deleted Files[/bold cyan] — [yellow]{len(deleted_entries)} found[/yellow]\n"
    )

    table = Table(border_style="red")
    table.add_column("Name", style="cyan")
    table.add_column("Size", justify="right", style="green")
    table.add_column("Start Cluster", justify="right", style="white")
    table.add_column("Deleted", style="red")
    table.add_column("Modified", style="dim")

    for entry in deleted_entries:
        ts = entry.last_modified.to_datetime()
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S") if ts else ""
        table.add_row(
            entry.full_name(),
            format_size(entry.file_size),
            str(entry.start_cluster),
            "Yes" if entry.deleted else "",
            ts_str,
        )

    console.print(table)


def _recover_files(
    console: Console,
    reader,
    bpb: FAT32BootSector,
    output: str,
    deleted_only: bool,
    json_output: bool,
) -> None:
    recovery = FAT32Recovery(reader, bpb)
    deleted_entries = recovery.find_deleted_entries()

    if deleted_only:
        targets = deleted_entries
    else:
        all_entries = walk_directory_tree(reader, bpb)
        targets = [e[1] for e in all_entries if not e[1].is_directory] + deleted_entries

    if not targets:
        console.print("[yellow]No files to recover.[/yellow]")
        return

    console.print(f"[bold cyan]Recovering {len(targets)} file(s)...[/bold cyan]\n")

    recovered: List[dict] = []

    for entry in targets:
        result = recovery.recover_deleted_file(entry)
        if result.data:
            saved_path = recovery.save_recovered(result, output_dir=output)
            status_color = "[red]DELETED[/red]" if result.deleted else "[green]OK[/green]"
            console.print(
                f"  {status_color} {result.original_name} "
                f"({format_size(len(result.data))}) -> [cyan]{saved_path}[/cyan]"
            )
            if result.recovery_notes:
                for note in result.recovery_notes:
                    console.print(f"       [dim]{note}[/dim]")
            recovered.append(result.to_dict())
        else:
            console.print(
                f"  [yellow]SKIP[/yellow] {result.original_name} ({result.recovery_status})"
            )

    console.print(f"\n[bold green]Recovery complete:[/bold green] {len(recovered)} file(s)")

    if json_output:
        report = {
            "filesystem": bpb.to_dict(),
            "recovered_files": recovered,
        }
        console.print(json.dumps(report, indent=2))
