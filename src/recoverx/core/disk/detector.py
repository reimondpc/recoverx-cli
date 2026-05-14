"""Disk detection module.

Uses psutil to enumerate mounted partitions and supplements with raw
block-device information from /sys/block on Linux. Runs in read-only mode.
"""

from __future__ import annotations

import os

import psutil


def get_disks() -> list[dict]:
    """Detect all connected disks and partitions.

    Returns a list of dictionaries, each containing:
      device, mountpoint, fstype, opts, total, used, free

    Detection covers mounted partitions via psutil and unmounted block
    devices on Linux via /sys/block (excluding loop devices).
    """
    seen: set[str] = set()
    disks: list[dict] = []

    for part in psutil.disk_partitions(all=True):
        seen.add(part.device)
        try:
            usage = psutil.disk_usage(part.mountpoint) if part.mountpoint else None
        except PermissionError:
            usage = None

        disks.append(
            {
                "device": part.device,
                "mountpoint": part.mountpoint or "N/A",
                "fstype": part.fstype or "unknown",
                "opts": part.opts,
                "total": usage.total if usage else 0,
                "used": usage.used if usage else 0,
                "free": usage.free if usage else 0,
            }
        )

    if os.name == "posix":
        _append_block_devices(disks, seen)

    return disks


def _append_block_devices(disks: list[dict], seen: set[str]) -> None:
    """Discover unmounted Linux block devices from /sys/block."""
    try:
        for entry in os.scandir("/sys/block"):
            name = entry.name
            if name.startswith("loop"):
                continue
            sys_dev = f"/dev/{name}"
            if sys_dev in seen:
                continue
            size_path = f"/sys/block/{name}/size"
            if os.path.exists(size_path):
                with open(size_path) as f:
                    sectors = int(f.read().strip())
                disks.append(
                    {
                        "device": sys_dev,
                        "mountpoint": "N/A",
                        "fstype": "block_device",
                        "opts": "",
                        "total": sectors * 512,
                        "used": 0,
                        "free": 0,
                    }
                )
    except PermissionError:
        pass
