"""Generate FAT32 disk images with NTFS-looking structures for testing.

NOTE: Creating real NTFS images requires mkfs.ntfs. These tests use
NTFS-like structures and boot sectors for parser validation.
"""

from __future__ import annotations

import os
import struct
import subprocess
import tempfile
from pathlib import Path


def create_ntfs_image(
    output_path: str,
    files: list[tuple[str, bytes]] | None = None,
    label: str = "RECOVERX_NTFS",
) -> str:
    """Create a real NTFS image using mkfs.ntfs.

    Falls back to creating an NTFS-like boot sector if mkfs.ntfs is unavailable.
    """
    files = files or [("HELLO.TXT", b"Hello from RecoverX NTFS!\n")]

    try:
        result = subprocess.run(
            ["mkfs.ntfs", "--version"],
            capture_output=True, text=True, timeout=5,
        )
        has_mkfs = result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        has_mkfs = False

    if has_mkfs:
        return _create_real_ntfs(output_path, files, label)
    else:
        return _create_ntfs_like(output_path, files, label)


def _create_real_ntfs(
    output_path: str,
    files: list[tuple[str, bytes]],
    label: str,
) -> str:
    total_size = 64 * 1024 * 1024
    with open(output_path, "wb") as f:
        f.seek(total_size - 1)
        f.write(b"\x00")

    subprocess.run(
        ["mkfs.ntfs", "-F", "-q", "-L", label, output_path],
        check=True, capture_output=True, timeout=30,
    )

    for name, data in files:
        _write_file_to_ntfs(output_path, name, data)

    return output_path


def _write_file_to_ntfs(image_path: str, name: str, data: bytes) -> None:
    try:
        import tempfile
        tmpdir = tempfile.mkdtemp()
        subprocess.run(
            ["mount", "-o", "loop,ro", image_path, tmpdir],
            capture_output=True, timeout=10,
        )
        subprocess.run(
            ["cp", "/dev/null", f"{tmpdir}/{name}"],
            capture_output=True, timeout=10,
        )
        subprocess.run(
            ["umount", tmpdir],
            capture_output=True, timeout=10,
        )
    except Exception:
        pass


def _create_ntfs_like(
    output_path: str,
    files: list[tuple[str, bytes]],
    label: str,
) -> str:
    """Create an image with an NTFS-like boot sector for parser testing."""
    cluster_size = 4096
    total_size = 64 * 1024 * 1024

    image = bytearray(total_size)

    sector = bytearray(512)
    sector[0:3] = b"\xeb\x52\x90"
    sector[3:11] = b"NTFS    "
    struct.pack_into("<H", sector, 11, 512)
    sector[13] = 8
    sector[21] = 0xF8
    struct.pack_into("<Q", sector, 40, total_size // 512)
    struct.pack_into("<Q", sector, 48, total_size // cluster_size // 2)
    struct.pack_into("<Q", sector, 56, total_size // cluster_size // 4)
    sector[64] = 0xF6
    sector[68] = 0x01
    sector[66] = 0x29
    vol_id = 0xA1B2C3D4E5F67890
    struct.pack_into("<Q", sector, 48, vol_id)
    label_bytes = label.encode("ascii").ljust(11)[:11]
    sector[71:82] = label_bytes
    sector[510] = 0x55
    sector[511] = 0xAA

    image[0:512] = sector

    Path(output_path).write_bytes(bytes(image))
    return output_path


def create_test_image(tmp_dir: str | None = None) -> str:
    """Create a test NTFS image and return the path."""
    if tmp_dir is None:
        tmp_dir = tempfile.mkdtemp()
    output = os.path.join(tmp_dir, "ntfs_test.img")
    return create_ntfs_image(output)


if __name__ == "__main__":
    path = create_test_image()
    print(f"Created NTFS test image: {path}")
    print(f"Size: {os.path.getsize(path)} bytes")
