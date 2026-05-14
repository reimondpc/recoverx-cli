from __future__ import annotations

import logging
import os
import platform

from rich.console import Console
from rich.table import Table

from recoverx.core.disk.detector import get_disks
from recoverx.core.filesystems.detector import detect_filesystem
from recoverx.core.utils.file_utils import format_size
from recoverx.core.utils.raw_reader import RawReader

logger = logging.getLogger("recoverx")


def run(console: Console, detailed: bool = False) -> None:
    console.print("[bold cyan]RecoverX[/bold cyan] — [yellow]Device Detection[/yellow]")
    console.print()

    disks = get_disks()

    if not disks:
        console.print("[yellow]No disks or partitions detected.[/yellow]")
        return

    summary_table = Table(title="Connected Devices", border_style="blue")
    summary_table.add_column("Device", style="cyan")
    summary_table.add_column("Size", justify="right", style="green")
    summary_table.add_column("Type", style="yellow")
    summary_table.add_column("Mount", style="white")
    summary_table.add_column("FS", style="magenta")

    for d in disks:
        fstype = d.get("fstype", "unknown")
        size = d.get("total", 0)
        summary_table.add_row(
            d["device"],
            format_size(size) if size else "N/A",
            fstype,
            d.get("mountpoint", "N/A"),
            _fs_icon(fstype),
        )

    console.print(summary_table)
    console.print()

    if detailed:
        for d in disks:
            _show_disk_details(console, d)


def _fs_icon(fstype: str) -> str:
    fstype_lower = fstype.lower()
    if "ntfs" in fstype_lower:
        return "NTFS"
    if "fat" in fstype_lower or "exfat" in fstype_lower:
        return "FAT"
    if "ext" in fstype_lower:
        return "ext"
    if "block_device" in fstype_lower:
        return "raw"
    return fstype[:6]


def _show_disk_details(console: Console, disk: dict) -> None:
    device = disk["device"]
    console.print(f"\n[bold]Device:[/bold] {device}")

    try:
        size = disk.get("total", 0)
        console.print(f"  Size:     {format_size(size) if size else 'N/A'}")

        if device.startswith("/dev/") and os.path.exists(device):
            if not os.access(device, os.R_OK):
                console.print(f"  [red]Access denied:[/red] {device} (try: sudo)")
                return

            try:
                with RawReader(device) as reader:
                    fs_info = detect_filesystem(reader)
                    console.print(f"  FS Type:  {fs_info.fstype}")
                    console.print(f"  Label:    {fs_info.label or 'N/A'}")
                    console.print(f"  Sector:   {fs_info.sector_size} B")
                    if fs_info.oem_id:
                        console.print(f"  OEM ID:   {fs_info.oem_id}")
            except Exception as e:
                logger.debug("Could not probe %s: %s", device, e)
                console.print(f"  [dim]Probe error: {e}[/dim]")
    except Exception as e:
        console.print(f"  [red]Error:[/red] {e}")

    console.print()


def detect_raw_devices() -> list[str]:
    devices: list[str] = []
    system = platform.system()

    if system == "Linux":
        for entry in os.scandir("/sys/block"):
            name = entry.name
            if name.startswith("loop") or name.startswith("ram"):
                continue
            dev_path = f"/dev/{name}"
            if os.path.exists(dev_path) and os.access(dev_path, os.R_OK):
                devices.append(dev_path)
            for i in range(16):
                part_path = f"{dev_path}{i}"
                if os.path.exists(part_path) and os.access(part_path, os.R_OK):
                    devices.append(part_path)
                alt_part = f"{dev_path}p{i}"
                if os.path.exists(alt_part) and os.access(alt_part, os.R_OK):
                    devices.append(alt_part)
                    break
    elif system == "Windows":
        for i in range(16):
            dev_path = f"\\\\.\\PhysicalDrive{i}"
            if os.path.exists(dev_path):
                try:
                    with open(dev_path, "rb") as f:
                        f.read(1)
                    devices.append(dev_path)
                except (OSError, PermissionError):
                    pass

    return sorted(set(devices))
