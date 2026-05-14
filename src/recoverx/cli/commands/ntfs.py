from __future__ import annotations

import json
import logging

import typer
from rich.console import Console
from rich.table import Table

from recoverx.core.filesystems.ntfs.boot_sector import parse_boot_sector, validate_boot_sector
from recoverx.core.filesystems.ntfs.recovery import NTFSRecovery
from recoverx.core.filesystems.ntfs.structures import NTFSBootSector
from recoverx.core.utils.file_utils import format_size
from recoverx.core.utils.raw_reader import RawReader

logger = logging.getLogger("recoverx")

ntfs_app = typer.Typer(
    name="ntfs",
    help="NTFS filesystem analysis and recovery commands.",
    rich_markup_mode="rich",
)


@ntfs_app.command()
def info(
    path: str = typer.Argument(..., help="Path to NTFS disk image or device."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Display NTFS boot sector information."""
    console = Console()

    with RawReader(path) as reader:
        sector0 = reader.read_at(0, 512)
        bpb = parse_boot_sector(sector0)

        if bpb is None:
            console.print("[red]Error:[/red] Not a valid NTFS boot sector.")
            raise typer.Exit(code=1)

        issues = validate_boot_sector(bpb)

        if json_output:
            data = bpb.to_dict()
            data["issues"] = issues
            console.print(json.dumps(data, indent=2))
            return

        console.print("[bold cyan]NTFS Boot Sector[/bold cyan]")
        console.print(f"  OEM ID:           [yellow]{bpb.oem_id}[/yellow]")
        console.print(f"  Bytes/Sector:     {bpb.bytes_per_sector}")
        console.print(f"  Sectors/Cluster:  {bpb.sectors_per_cluster}")
        console.print(f"  Cluster Size:     [green]{format_size(bpb.cluster_size)}[/green]")
        console.print(f"  Total Sectors:    {bpb.total_sectors:,}")
        console.print(f"  Total Size:       [green]{format_size(bpb.total_size)}[/green]")
        console.print(f"  MFT Cluster:      {bpb.mft_cluster}")
        console.print(f"  MFT Mirror:       {bpb.mft_mirror_cluster}")
        console.print(f"  Bytes/FileRecord: {bpb.bytes_per_file_record}")
        console.print(f"  Volume Serial:    [cyan]{bpb.volume_serial}[/cyan]")
        sig_str = "[green]Valid[/green]" if bpb.signature_valid else "[red]Invalid[/red]"
        console.print(f"  Signature:        {sig_str}")

        if issues:
            console.print("\n[bold yellow]Issues:[/bold yellow]")
            for issue in issues:
                console.print(f"  [yellow]*[/yellow] {issue}")
        else:
            console.print("\n[green]No issues detected.[/green]")


@ntfs_app.command()
def mft(
    path: str = typer.Argument(..., help="Path to NTFS disk image or device."),
    limit: int = typer.Option(20, "--limit", "-n", help="Max MFT records to show."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """List MFT records (active files and directories)."""
    console = Console()
    _with_bpb(console, path,
              lambda reader, bpb: _list_mft(console, reader, bpb, limit, json_output))


@ntfs_app.command()
def deleted(
    path: str = typer.Argument(..., help="Path to NTFS disk image or device."),
    limit: int = typer.Option(50, "--limit", "-n", help="Max deleted records."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """List deleted entries found in the MFT."""
    console = Console()
    _with_bpb(console, path,
              lambda reader, bpb: _list_deleted(console, reader, bpb, limit, json_output))


@ntfs_app.command()
def resident(
    path: str = typer.Argument(..., help="Path to NTFS disk image or device."),
    output: str = typer.Option("recovered", "--output", "-o", help="Output directory."),
    limit: int = typer.Option(50, "--limit", "-n", help="Max files to recover."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Recover resident (small) files from MFT records."""
    console = Console()
    _with_bpb(console, path, lambda reader, bpb: _recover_resident(
        console, reader, bpb, output, limit, json_output
    ))


def _with_bpb(console: Console, path: str, callback) -> None:
    with RawReader(path) as reader:
        sector0 = reader.read_at(0, 512)
        bpb = parse_boot_sector(sector0)
        if bpb is None:
            console.print("[red]Error:[/red] Not a valid NTFS boot sector.")
            raise typer.Exit(code=1)
        callback(reader, bpb)


def _list_mft(console: Console, reader, bpb: NTFSBootSector, limit: int, json_output: bool) -> None:
    rec = NTFSRecovery(reader, bpb)
    records = rec.walk_mft(max_records=limit)

    if json_output:
        data = {"filesystem": bpb.to_dict(), "mft_records": [r.to_dict() for r in records]}
        console.print(json.dumps(data, indent=2))
        return

    msg = f"[bold cyan]NTFS MFT Records[/bold cyan] — [yellow]{len(records)} shown[/yellow]"
    console.print(msg)

    table = Table(border_style="cyan")
    table.add_column("Record", style="white", justify="right")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="yellow")
    table.add_column("Size", justify="right", style="green")
    table.add_column("Status", style="red")

    for r in records:
        status = "[red]DELETED[/red]" if r.is_deleted else "[green]ACTIVE[/green]"
        table.add_row(
            str(r.header.mft_record_number),
            r.name or "-",
            "DIR" if r.is_directory else "FILE",
            format_size(r.file_name.real_size) if r.file_name else "",
            status,
        )

    console.print(table)


def _list_deleted(
    console: Console, reader, bpb: NTFSBootSector, limit: int, json_output: bool
) -> None:
    rec = NTFSRecovery(reader, bpb)
    deleted_records = rec.find_deleted_entries(max_records=limit)

    if json_output:
        data = {
            "filesystem": bpb.to_dict(),
            "deleted_files": [r.to_dict() for r in deleted_records],
        }
        console.print(json.dumps(data, indent=2))
        return

    if not deleted_records:
        console.print("[yellow]No deleted files found in MFT.[/yellow]")
        return

    console.print(
        f"[bold cyan]Deleted NTFS Files[/bold cyan] — "
        f"[yellow]{len(deleted_records)} found[/yellow]\n"
    )

    table = Table(border_style="red")
    table.add_column("MFT Record", style="white", justify="right")
    table.add_column("Name", style="cyan")
    table.add_column("Size", justify="right", style="green")
    table.add_column("Resident", style="yellow")

    for r in deleted_records:
        table.add_row(
            str(r.header.mft_record_number),
            r.name or "-",
            format_size(r.file_name.real_size) if r.file_name else "",
            "[green]Yes[/green]" if r.resident and r.data_resident else "[dim]No[/dim]",
        )

    console.print(table)
    console.print("\nTip: Use [cyan]recoverx ntfs resident[/cyan] to extract resident files.")


def _recover_resident(
    console: Console, reader, bpb: NTFSBootSector,
    output: str, limit: int, json_output: bool,
) -> None:
    rec = NTFSRecovery(reader, bpb)
    resident_records = rec.find_resident_files(max_records=limit)

    if not resident_records:
        console.print("[yellow]No resident files found.[/yellow]")
        return

    msg = f"[bold cyan]Recovering {len(resident_records)} resident file(s)...[/bold cyan]"
    console.print(msg)

    recovered_list: list[dict] = []
    for record in resident_records:
        result = rec.recover_resident_file(record)
        if result.data:
            saved_path = rec.save_recovered(result, output_dir=output)
            status_color = "[red]DELETED[/red]" if result.deleted else "[green]OK[/green]"
            console.print(
                f"  {status_color} {result.original_name} "
                f"({format_size(len(result.data))}) -> [cyan]{saved_path}[/cyan]"
            )
            if result.recovery_notes:
                for note in result.recovery_notes:
                    console.print(f"       [dim]{note}[/dim]")
            recovered_list.append(result.to_dict())
        else:
            console.print(
                f"  [yellow]SKIP[/yellow] {result.original_name} ({result.recovery_status})"
            )

    console.print(
        f"\n[bold green]Recovery complete:[/bold green] {len(recovered_list)} file(s)"
    )

    if json_output:
        report = {"filesystem": bpb.to_dict(), "recovered_files": recovered_list}
        console.print(json.dumps(report, indent=2))
