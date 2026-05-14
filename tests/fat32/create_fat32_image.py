"""Generate reproducible FAT32 disk images for testing.

Creates a small FAT32 image with known files, deleted files,
and directory structure. Pure Python, no external dependencies.
"""

from __future__ import annotations

import os
import struct
import tempfile
from pathlib import Path

# FAT32 constants
BYTES_PER_SECTOR = 512
SECTORS_PER_CLUSTER = 4
CLUSTER_SIZE = BYTES_PER_SECTOR * SECTORS_PER_CLUSTER  # 2048
RESERVED_SECTORS = 32
FAT_COUNT = 2
FAT_SIZE_SECTORS = 32  # 32 sectors * 512 = 16KB per FAT = 4096 entries
ROOT_CLUSTER = 2
TOTAL_SECTORS = 51200  # 25 MB
DATA_START = (RESERVED_SECTORS + FAT_COUNT * FAT_SIZE_SECTORS) * BYTES_PER_SECTOR
TOTAL_DATA_CLUSTERS = (
    TOTAL_SECTORS - RESERVED_SECTORS - FAT_COUNT * FAT_SIZE_SECTORS
) // SECTORS_PER_CLUSTER

DIR_ATTR_ARCHIVE = 0x20
DIR_ATTR_DIRECTORY = 0x10
DIR_ATTR_VOLUME = 0x08
DELETED_MARKER = 0xE5


def make_boot_sector(volume_label: str = "RECOVERX_TEST") -> bytes:
    sector = bytearray(512)

    sector[0:3] = b"\xeb\x58\x90"
    sector[3:11] = b"RECOVERX"
    struct.pack_into("<H", sector, 11, BYTES_PER_SECTOR)
    sector[13] = SECTORS_PER_CLUSTER
    struct.pack_into("<H", sector, 14, RESERVED_SECTORS)
    sector[16] = FAT_COUNT
    struct.pack_into("<H", sector, 17, 0)
    struct.pack_into("<H", sector, 19, 0)
    sector[21] = 0xF8
    struct.pack_into("<H", sector, 22, 0)
    struct.pack_into("<H", sector, 24, 63)
    struct.pack_into("<H", sector, 26, 255)
    struct.pack_into("<I", sector, 28, 0)
    struct.pack_into("<I", sector, 32, TOTAL_SECTORS)
    struct.pack_into("<I", sector, 36, FAT_SIZE_SECTORS)
    struct.pack_into("<H", sector, 40, 0x0000)
    struct.pack_into("<H", sector, 42, 0)
    struct.pack_into("<I", sector, 44, ROOT_CLUSTER)
    struct.pack_into("<H", sector, 48, 1)
    struct.pack_into("<H", sector, 50, 6)
    sector[64] = 0x80
    sector[66] = 0x29
    struct.pack_into("<I", sector, 67, 0xA1B2C3D4)
    label = volume_label.encode("ascii").ljust(11)[:11]
    sector[71:82] = label
    sector[82:90] = b"FAT32   "

    sector[510] = 0x55
    sector[511] = 0xAA

    return bytes(sector)


def make_fsinfo_sector() -> bytes:
    sector = bytearray(512)
    sector[0:4] = b"RRaA"
    sector[484:488] = b"rrAa"
    sector[488:492] = struct.pack("<I", TOTAL_DATA_CLUSTERS)
    sector[492:496] = struct.pack("<I", 3)
    sector[508:512] = b"\x00\x00\x55\xaa"
    return bytes(sector)


def make_fat_entry(cluster: int, value: int) -> bytes:
    return struct.pack("<I", value & 0x0FFFFFFF)


def make_directory_entry(
    name: str,
    ext: str,
    attr: int,
    cluster_high: int,
    cluster_low: int,
    file_size: int,
    deleted: bool = False,
) -> bytes:
    entry = bytearray(32)
    name_raw = name.ljust(8)[:8].upper().encode("ascii")
    ext_raw = ext.ljust(3)[:3].upper().encode("ascii")

    if deleted:
        name_raw = bytearray(name_raw)
        name_raw[0] = DELETED_MARKER

    entry[0:8] = name_raw
    entry[8:11] = ext_raw
    entry[11] = attr
    entry[13] = 0
    struct.pack_into("<H", entry, 14, 0)  # create time
    struct.pack_into("<H", entry, 16, 0)  # create date
    struct.pack_into("<H", entry, 18, 0)  # access date
    struct.pack_into("<H", entry, 20, cluster_high)
    struct.pack_into("<H", entry, 22, 0)  # mod time
    struct.pack_into("<H", entry, 24, 0)  # mod date
    struct.pack_into("<H", entry, 26, cluster_low)
    struct.pack_into("<I", entry, 28, file_size)
    return bytes(entry)


def make_dot_entries(cluster: int, parent_cluster: int) -> bytes:
    dot = make_directory_entry(".", "", DIR_ATTR_DIRECTORY, cluster >> 16, cluster & 0xFFFF, 0)
    dotdot = make_directory_entry(
        "..", "", DIR_ATTR_DIRECTORY, parent_cluster >> 16, parent_cluster & 0xFFFF, 0
    )
    return dot + dotdot


def create_fat32_image(
    output_path: str,
    files: list[tuple[str, bytes]] | None = None,
    deleted_files: list[tuple[str, bytes]] | None = None,
    subdirs: list[tuple[str, list[tuple[str, bytes]]]] | None = None,
) -> str:
    if files is None:
        files = [
            ("README.TXT", b"This is a test FAT32 image.\n" * 10),
            ("HELLO.TXT", b"Hello, RecoverX!\n"),
            ("IMAGE.JPG", b"\xff\xd8\xff\x00\xff\xd9".ljust(1024, b"\x00")),
            ("DATA.BIN", bytes(range(256)) * 4),
        ]

    if deleted_files is None:
        deleted_files = [
            ("SECRET.DAT", b"DELETED FILE CONTENT\n" * 20),
            ("OLD.DOC", b"This file was deleted.\n" * 5),
        ]

    if subdirs is None:
        subdirs = [
            ("SUBDIR", [("NESTED.TXT", b"Nested file in subdirectory.\n" * 3)]),
        ]

    total_sectors = max(
        TOTAL_SECTORS, RESERVED_SECTORS + FAT_COUNT * FAT_SIZE_SECTORS + 100 * SECTORS_PER_CLUSTER
    )
    image = bytearray(total_sectors * BYTES_PER_SECTOR)

    image[0:512] = make_boot_sector()
    image[BYTES_PER_SECTOR : BYTES_PER_SECTOR + 512] = make_fsinfo_sector()

    # Initialize FAT with reserved entries
    fat_start = RESERVED_SECTORS * BYTES_PER_SECTOR
    fat = bytearray(FAT_SIZE_SECTORS * BYTES_PER_SECTOR)

    def set_fat(cluster: int, value: int) -> None:
        offset = cluster * 4
        fat[offset : offset + 4] = make_fat_entry(cluster, value)

    set_fat(0, 0x0FFFFFF8)  # media descriptor
    set_fat(1, 0x0FFFFFFF)  # reserved
    set_fat(ROOT_CLUSTER, 0x0FFFFFFF)  # root dir is 1 cluster

    next_cluster = ROOT_CLUSTER + 1

    data_start_bytes = DATA_START

    def write_file_to_clusters(file_data: bytes) -> tuple[int, int, list[int]]:
        nonlocal next_cluster
        clusters_needed = max(1, (len(file_data) + CLUSTER_SIZE - 1) // CLUSTER_SIZE)
        start_cluster = next_cluster
        chain: list[int] = []

        for i in range(clusters_needed):
            cluster = next_cluster
            chain.append(cluster)
            cluster_offset = data_start_bytes + (cluster - 2) * CLUSTER_SIZE
            chunk = file_data[i * CLUSTER_SIZE : (i + 1) * CLUSTER_SIZE]
            image[cluster_offset : cluster_offset + len(chunk)] = chunk
            next_cluster += 1

        for i, c in enumerate(chain):
            if i == len(chain) - 1:
                set_fat(c, 0x0FFFFFFF)
            else:
                set_fat(c, chain[i + 1])

        return start_cluster, len(chain), chain

    # Root directory entries
    root_cluster_offset = data_start_bytes + (ROOT_CLUSTER - 2) * CLUSTER_SIZE
    root_dir = bytearray(CLUSTER_SIZE)
    entry_offset = 0

    def add_entry(entry_bytes: bytes) -> None:
        nonlocal entry_offset
        root_dir[entry_offset : entry_offset + len(entry_bytes)] = entry_bytes
        entry_offset += 32

    # Add volume label
    add_entry(make_directory_entry("RECOVERX_TE", "ST", DIR_ATTR_VOLUME, 0, 0, 0))

    # Write regular files
    for name, data in files:
        base = name.upper().rsplit(".", 1)
        fname = base[0][:8]
        fext = base[1][:3] if len(base) > 1 else ""
        sc, _, _ = write_file_to_clusters(data)
        add_entry(
            make_directory_entry(fname, fext, DIR_ATTR_ARCHIVE, sc >> 16, sc & 0xFFFF, len(data))
        )

    # Write deleted files
    for name, data in deleted_files:
        base = name.upper().rsplit(".", 1)
        fname = base[0][:8]
        fext = base[1][:3] if len(base) > 1 else ""
        sc, _, _ = write_file_to_clusters(data)
        add_entry(
            make_directory_entry(
                fname, fext, DIR_ATTR_ARCHIVE, sc >> 16, sc & 0xFFFF, len(data), deleted=True
            )
        )

    # Write subdirectories
    for dirname, dirfiles in subdirs:
        dname = dirname.upper().ljust(8)[:8]
        sc, _, _ = write_file_to_clusters(b"")
        sub_cluster = sc

        add_entry(make_directory_entry(dname, "", DIR_ATTR_DIRECTORY, sc >> 16, sc & 0xFFFF, 0))

        sub_offset = data_start_bytes + (sub_cluster - 2) * CLUSTER_SIZE
        sub_data = bytearray(CLUSTER_SIZE)
        sub_entry_off = 0

        sub_data[0:32] = make_dot_entries(sub_cluster, ROOT_CLUSTER)
        sub_entry_off = 64

        for sf_name, sf_data in dirfiles:
            base = sf_name.upper().rsplit(".", 1)
            sfname = base[0][:8]
            sfext = base[1][:3] if len(base) > 1 else ""
            ssc, _, _ = write_file_to_clusters(sf_data)
            entry = make_directory_entry(
                sfname, sfext, DIR_ATTR_ARCHIVE, ssc >> 16, ssc & 0xFFFF, len(sf_data)
            )
            sub_data[sub_entry_off : sub_entry_off + 32] = entry
            sub_entry_off += 32

        image[sub_offset : sub_offset + CLUSTER_SIZE] = sub_data

    # Set root directory
    image[root_cluster_offset : root_cluster_offset + CLUSTER_SIZE] = root_dir

    # Write FATs
    for i in range(FAT_COUNT):
        fat_offset = fat_start + i * FAT_SIZE_SECTORS * BYTES_PER_SECTOR
        image[fat_offset : fat_offset + len(fat)] = fat

    Path(output_path).write_bytes(bytes(image))
    return output_path


def create_test_image(tmp_dir: str | None = None) -> str:
    """Create a test FAT32 image at a temporary path and return the path."""
    if tmp_dir is None:
        tmp_dir = tempfile.mkdtemp()
    output = os.path.join(tmp_dir, "fat32_test.img")
    return create_fat32_image(output)


if __name__ == "__main__":
    path = create_test_image()
    print(f"Created FAT32 test image: {path}")
    print(f"Size: {os.path.getsize(path)} bytes")
