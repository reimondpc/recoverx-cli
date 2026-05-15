from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import typer
from rich.console import Console
from rich.table import Table

from recoverx.core.filesystems.ntfs.boot_sector import parse_boot_sector, validate_boot_sector
from recoverx.core.filesystems.ntfs.recovery import NTFSRecovery
from recoverx.core.filesystems.ntfs.structures import MFTRecord, NTFSBootSector, RecoveredNTFSFile
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


@ntfs_app.command()
def recover(
    path: str = typer.Argument(..., help="Path to NTFS disk image or device."),
    output: str = typer.Option("recovered", "--output", "-o", help="Output directory."),
    limit: int = typer.Option(50, "--limit", "-n", help="Max files to recover."),
    deleted_only: bool = typer.Option(False, "--deleted-only", help="Only recover deleted files."),
    non_resident_only: bool = typer.Option(
        False, "--non-resident-only", help="Only recover non-resident files."
    ),
    verify_hashes: bool = typer.Option(False, "--verify-hashes", help="Verify SHA-256 hashes."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
    threads: int = typer.Option(1, "--threads", "-t", help="Worker threads (experimental)."),
) -> None:
    """Recover files from NTFS (resident and non-resident)."""
    console = Console()
    _with_bpb(console, path, lambda reader, bpb: _recover_files(
        console, reader, bpb, output, limit,
        deleted_only, non_resident_only, verify_hashes, json_output, threads,
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


def _recover_single_file(
    path: str, bpb: NTFSBootSector, record: MFTRecord, output: str,
) -> tuple[RecoveredNTFSFile, str] | None:
    """Recover a single file with its own reader (thread-safe)."""
    with RawReader(path) as reader:
        ntfs = NTFSRecovery(reader, bpb)
        if record.resident and record.data_resident:
            result = ntfs.recover_resident_file(record)
        elif record.has_non_resident_data:
            result = ntfs.recover_non_resident_file(record)
        else:
            return None
        if result.data:
            saved_path = ntfs.save_recovered(result, output_dir=output)
            return result, saved_path
    return None


def _recover_files(
    console: Console, reader, bpb: NTFSBootSector,
    output: str, limit: int,
    deleted_only: bool, non_resident_only: bool,
    verify_hashes: bool, json_output: bool, threads: int,
) -> None:
    rec = NTFSRecovery(reader, bpb)

    all_records = rec.walk_mft(max_records=limit)
    candidates = [r for r in all_records if not r.is_directory]

    if deleted_only:
        candidates = [r for r in candidates if r.is_deleted]
    if non_resident_only:
        candidates = [r for r in candidates if r.has_non_resident_data]
    else:
        candidates = [
            r for r in candidates
            if (r.resident and r.data_resident) or r.has_non_resident_data
        ]

    if not candidates:
        console.print("[yellow]No recoverable files found.[/yellow]")
        return

    msg = f"[bold cyan]Recovering {len(candidates)} file(s)...[/bold cyan]"
    console.print(msg)
    console.print()

    recovered_list: list[dict] = []

    if threads > 1:
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = {
                executor.submit(
                    _recover_single_file, reader.path, bpb, record, output,
                ): record
                for record in candidates
            }
            for future in as_completed(futures):
                result_tuple = future.result()
                if result_tuple:
                    result, saved_path = result_tuple
                    if not json_output:
                        _print_recovery_result(console, result, saved_path)
                    recovered_list.append(result.to_dict())
                else:
                    record = futures[future]
                    if not json_output:
                        console.print(
                            f"  [yellow]SKIP[/yellow] {record.name or '?'} (no recoverable data)"
                        )
    else:
        for record in candidates:
            result_tuple = _recover_single_file(
                reader.path, bpb, record, output,
            )
            if result_tuple:
                result, saved_path = result_tuple
                if not json_output:
                    _print_recovery_result(console, result, saved_path)
                recovered_list.append(result.to_dict())
            else:
                if not json_output:
                    console.print(
                        f"  [yellow]SKIP[/yellow] {record.name or '?'} (no recoverable data)"
                    )

    if json_output:
        report = {
            "filesystem": bpb.to_dict(),
            "recovered_files": recovered_list,
        }
        console.print(json.dumps(report, indent=2))
        return

    console.print(
        f"\n[bold green]Recovery complete:[/bold green] {len(recovered_list)} file(s)"
    )


def _print_recovery_result(console: Console, result, saved_path: str) -> None:
    status_color = "[red]DELETED[/red]" if result.deleted else "[green]OK[/green]"
    data_size = format_size(len(result.data))

    if result.resident:
        console.print(
            f"  {status_color} {result.original_name} "
            f"({data_size}) -> [cyan]{saved_path}[/cyan]"
        )
    else:
        fragment_info = ""
        if result.fragmented:
            fragment_info = f" [yellow]({result.run_count} runs)[/yellow]"
        sparse_tag = " [cyan][SPARSE][/cyan]" if result.sparse else ""

        console.print(
            f"  {status_color} {result.original_name} "
            f"({data_size}){fragment_info}{sparse_tag} -> [cyan]{saved_path}[/cyan]"
        )

    if result.recovery_notes:
        for note in result.recovery_notes:
            console.print(f"       [dim]{note}[/dim]")


@ntfs_app.command()
def analyse(
    path: str = typer.Argument(..., help="Path to NTFS disk image or device."),
    record: int = typer.Option(0, "--record", "-r", help="MFT record number to analyse."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Analyse non-resident runlists for a specific MFT record."""
    console = Console()

    with RawReader(path) as reader:
        sector0 = reader.read_at(0, 512)
        bpb = parse_boot_sector(sector0)
        if bpb is None:
            console.print("[red]Error:[/red] Not a valid NTFS boot sector.")
            raise typer.Exit(code=1)

        rec = NTFSRecovery(reader, bpb)
        records = rec.walk_mft(max_records=record + 1 if record > 0 else 50)

        target = None
        for r in records:
            if r.header.mft_record_number == record:
                target = r
                break

        if target is None:
            console.print(f"[red]MFT record {record} not found.[/red]")
            raise typer.Exit(code=1)

        analysis = rec.analyse_runs(target)

        if json_output:
            d = {
                "mft_record": target.to_dict(),
                "run_analysis": analysis,
            }
            console.print(json.dumps(d, indent=2))
            return

        if not analysis["has_runs"]:
            console.print("[yellow]No non-resident data runs found.[/yellow]")
            return

        console.print(f"[bold cyan]Runlist Analysis — MFT Record {record}[/bold cyan]")
        console.print(f"  File:          [yellow]{target.name}[/yellow]")
        console.print(f"  Real Size:     {format_size(analysis['real_size'])}")
        console.print(f"  Allocated:     {format_size(analysis['allocated_size'])}")
        frag_str = "[red]Yes[/red]" if analysis["is_fragmented"] else "[green]No[/green]"
        console.print(f"  Fragmented:    {frag_str}")
        console.print(f"  Run Count:     {analysis['run_count']}")
        sparse_str = "[cyan]Yes[/cyan]" if analysis["is_sparse"] else "[dim]No[/dim]"
        console.print(f"  Sparse:        {sparse_str}")

        if analysis["sparse_info"]:
            si = analysis["sparse_info"]
            console.print("\n  [bold cyan]Sparse Info:[/bold cyan]")
            console.print(f"    Virtual Size:    {format_size(si['virtual_size'])}")
            console.print(f"    Allocated Size:  {format_size(si['allocated_size'])}")
            console.print(f"    Sparse Ratio:    {si['sparse_ratio']:.1%}")
            console.print(f"    Sparse Clusters: {si['sparse_clusters']:,}")

        recoverable = analysis["recoverable_bytes"]
        lost = analysis["recoverable_lost"]
        console.print(f"\n  [bold]Recoverable:[/bold] {format_size(recoverable)}")
        if lost > 0:
            console.print(f"  [red]Lost:[/red]         {format_size(lost)}")

        if analysis["validation_issues"]:
            console.print("\n  [bold yellow]Validation Issues:[/bold yellow]")
            for issue in analysis["validation_issues"]:
                color = "[red]" if issue["severity"] == "error" else "[yellow]"
                console.print(f"    {color}[{issue['code']}][/] {issue['message']}")

        console.print("\n  [bold]Data Runs:[/bold]")
        for i, br in enumerate(analysis["byte_runs"]):
            if br["is_sparse"]:
                console.print(
                    f"    Run {i}: VCN [{br['vcn_start']}-{br['vcn_end']}] "
                    f"[cyan]SPARSE[/cyan] ({format_size(br['byte_length'])})"
                )
            else:
                console.print(
                    f"    Run {i}: VCN [{br['vcn_start']}-{br['vcn_end']}] "
                    f"LCN {br['lcn']} ({format_size(br['byte_length'])}) "
                    f"@ offset {format_size(br['byte_offset'])}"
                )


@ntfs_app.command()
def usn(
    path: str = typer.Argument(..., help="Path to NTFS disk image or device."),
    limit: int = typer.Option(50, "--limit", "-n", help="Max USN records."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Parse USN journal entries from $UsnJrnl."""
    console = Console()
    with RawReader(path) as reader:
        sector0 = reader.read_at(0, 512)
        bpb = parse_boot_sector(sector0)
        if bpb is None:
            console.print("[red]Error:[/red] Not a valid NTFS boot sector.")
            raise typer.Exit(code=1)

        from recoverx.core.filesystems.ntfs.usn.parser import USNParser

        parser = USNParser(reader, bpb)
        records = parser.parse_raw()

        if not records:
            console.print("[yellow]No USN records found.[/yellow]")
            return

        if limit > 0:
            records = records[:limit]

        if json_output:
            console.print(json.dumps(
                {"usn_records": [r.to_dict() for r in records]}, indent=2,
            ))
            return

        console.print(
            f"[bold cyan]USN Journal[/bold cyan] — "
            f"[yellow]{len(records)} records[/yellow]\n"
        )

        table = Table(border_style="cyan")
        table.add_column("USN", style="white", justify="right")
        table.add_column("Timestamp", style="cyan")
        table.add_column("File", style="yellow")
        table.add_column("Reasons")
        table.add_column("MFT Ref", justify="right")

        for r in records:
            ts = r.timestamp.strftime("%Y-%m-%d %H:%M:%S") if r.timestamp else "-"
            reasons = ", ".join(
                n.replace("USN_REASON_", "")[:20] for n in r.reason_names[:3]
            )
            table.add_row(
                str(r.usn),
                ts,
                r.file_name or "-",
                reasons,
                str(r.file_reference),
            )

        console.print(table)


@ntfs_app.command()
def logfile(
    path: str = typer.Argument(..., help="Path to NTFS disk image or device."),
    limit: int = typer.Option(50, "--limit", "-n", help="Max log records."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Parse $LogFile transaction records."""
    console = Console()
    with RawReader(path) as reader:
        sector0 = reader.read_at(0, 512)
        bpb = parse_boot_sector(sector0)
        if bpb is None:
            console.print("[red]Error:[/red] Not a valid NTFS boot sector.")
            raise typer.Exit(code=1)

        from recoverx.core.filesystems.ntfs.logfile.parser import LogFileParser

        parser = LogFileParser(reader, bpb)
        result = parser.parse()

        if not result["found"]:
            console.print("[yellow]No $LogFile data found.[/yellow]")
            return

        if json_output:
            console.print(json.dumps(result, indent=2, default=str))
            return

        console.print(
            f"[bold cyan]$LogFile Analysis[/bold cyan]\n"
        )
        console.print(f"  Pages:         {result['page_count']}")
        console.print(f"  Page Size:     {result['page_size']} bytes")
        console.print(f"  Restart Pages: {len(result['restart_pages'])}")
        console.print(f"  Log Records:   {result['total_records_found']}")

        if result["restart_areas"]:
            console.print("\n[bold]Restart Areas:[/bold]")
            for ra in result["restart_areas"]:
                console.print(f"  Last LSN: {ra['last_lsn']}  Oldest LSN: {ra['oldest_lsn']}")

        if result["records"]:
            console.print(f"\n[bold]Log Records ({min(limit, len(result['records']))} shown):[/bold]")
            table = Table(border_style="yellow")
            table.add_column("LSN", style="white", justify="right")
            table.add_column("Type", style="cyan")
            table.add_column("Operation", style="yellow")
            table.add_column("MFT Ref", justify="right")

            for rec in result["records"][:limit]:
                table.add_row(
                    str(rec["lsn"]),
                    rec["record_type_name"][:20],
                    rec["redo_operation"][:20],
                    str(rec["target_mft"]),
                )
            console.print(table)
