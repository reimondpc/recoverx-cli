from __future__ import annotations

import logging
import struct
from dataclasses import dataclass

from recoverx.core.utils.raw_reader import RawReader

logger = logging.getLogger("recoverx")

FS_UNKNOWN = "unknown"
FS_FAT12 = "FAT12"
FS_FAT16 = "FAT16"
FS_FAT32 = "FAT32"
FS_EXFAT = "exFAT"
FS_NTFS = "NTFS"
FS_EXT234 = "ext2/3/4"


@dataclass
class FSInfo:
    fstype: str = FS_UNKNOWN
    label: str = ""
    sector_size: int = 512
    total_sectors: int = 0
    total_size: int = 0
    oem_id: str = ""
    volume_id: str = ""

    def to_dict(self) -> dict:
        return {
            "fstype": self.fstype,
            "label": self.label,
            "sector_size": self.sector_size,
            "total_sectors": self.total_sectors,
            "total_size": self.total_size,
            "oem_id": self.oem_id,
            "volume_id": self.volume_id,
        }


def detect_filesystem(reader: RawReader) -> FSInfo:
    info = FSInfo(total_size=reader.size)

    if reader.size < 512:
        return info

    sector0 = reader.read_at(0, 512)
    info.sector_size = _detect_sector_size(sector0)
    info.total_sectors = reader.size // info.sector_size

    ext4_data = reader.read_at(0, min(2048, reader.size))
    detected = _check_ext4(ext4_data)
    if detected:
        return detected

    detected = _check_ntfs(sector0)
    if detected:
        return detected

    detected = _check_exfat(sector0)
    if detected:
        return detected

    detected = _check_fat(sector0)
    if detected:
        return detected

    return info


def _detect_sector_size(sector0: bytes) -> int:
    if len(sector0) < 512:
        return 512
    return 512


def _check_fat(sector0: bytes) -> FSInfo | None:
    if len(sector0) < 64:
        return None

    bs_jmp = sector0[0:3]
    oem = sector0[3:11].decode("ascii", errors="replace").strip()

    if bs_jmp not in (b"\xeb\x3c\x90", b"\xeb\x58\x90", b"\xeb\x76\x90", b"\xe9\x00\x00"):
        if oem not in ("MSDOS5.0", "MSWIN4.0", "MSWIN4.1", "mkdosfs", "FAT32", "NTFS"):
            return None

    try:
        bytes_per_sector = struct.unpack_from("<H", sector0, 11)[0]
        sectors_per_cluster = sector0[13]
        reserved_sectors = struct.unpack_from("<H", sector0, 14)[0]
        num_fats = sector0[16]
        root_entries = struct.unpack_from("<H", sector0, 17)[0]
        total_sectors_16 = struct.unpack_from("<H", sector0, 19)[0]
        sectors_per_fat_16 = struct.unpack_from("<H", sector0, 22)[0]
        total_sectors_32 = struct.unpack_from("<I", sector0, 32)[0]

        total_sectors = total_sectors_16 if total_sectors_16 != 0 else total_sectors_32

        sectors_per_fat_32 = 0
        if sectors_per_fat_16 == 0:
            sectors_per_fat_32 = struct.unpack_from("<I", sector0, 36)[0]

        root_dir_sectors = ((root_entries * 32) + (bytes_per_sector - 1)) // bytes_per_sector
        fat_size = sectors_per_fat_16 if sectors_per_fat_16 != 0 else sectors_per_fat_32
        total_data_sectors = total_sectors - (
            reserved_sectors + (num_fats * fat_size) + root_dir_sectors
        )
        clusters = total_data_sectors // sectors_per_cluster if sectors_per_cluster > 0 else 0

        label_raw = sector0[43:54]
        label = label_raw.decode("ascii", errors="replace").strip()

        if clusters < 4085:
            return FSInfo(
                fstype=FS_FAT12,
                label=label,
                sector_size=bytes_per_sector,
                total_sectors=total_sectors,
                total_size=total_sectors * bytes_per_sector,
                oem_id=oem,
            )
        elif clusters < 65525:
            return FSInfo(
                fstype=FS_FAT16,
                label=label,
                sector_size=bytes_per_sector,
                total_sectors=total_sectors,
                total_size=total_sectors * bytes_per_sector,
                oem_id=oem,
            )
        else:
            return FSInfo(
                fstype=FS_FAT32,
                label=label,
                sector_size=bytes_per_sector,
                total_sectors=total_sectors,
                total_size=total_sectors * bytes_per_sector,
                oem_id=oem,
            )

    except struct.error:
        return None


def _check_ntfs(sector0: bytes) -> FSInfo | None:
    if len(sector0) < 64:
        return None

    oem = sector0[3:11]
    if oem != b"NTFS    ":
        return None

    try:
        bytes_per_sector = struct.unpack_from("<H", sector0, 11)[0]
        total_sectors = struct.unpack_from("<Q", sector0, 40)[0]
        label_raw = sector0[11:19]
        label = label_raw.decode("ascii", errors="replace").strip()

        volume_id_bytes = sector0[48:56]
        volume_id = "-".join(
            [
                volume_id_bytes[0:4].hex().upper(),
                volume_id_bytes[4:6].hex().upper(),
                volume_id_bytes[6:8].hex().upper(),
            ]
        )

        return FSInfo(
            fstype=FS_NTFS,
            label=label,
            sector_size=bytes_per_sector,
            total_sectors=total_sectors,
            total_size=total_sectors * bytes_per_sector,
            oem_id="NTFS",
            volume_id=volume_id,
        )
    except struct.error:
        return None


def _check_exfat(sector0: bytes) -> FSInfo | None:
    if len(sector0) < 120:
        return None

    if sector0[3:11] != b"EXFAT   ":
        return None

    try:
        bytes_per_sector = 1 << struct.unpack_from("<B", sector0, 108)[0]
        total_sectors = struct.unpack_from("<Q", sector0, 72)[0]
        label_raw = sector0[112:123]
        label = label_raw.decode("utf-16-le", errors="replace").strip("\x00").strip()

        return FSInfo(
            fstype=FS_EXFAT,
            label=label,
            sector_size=bytes_per_sector,
            total_sectors=total_sectors,
            total_size=total_sectors * bytes_per_sector,
            oem_id="EXFAT",
        )
    except struct.error:
        return None


def _check_ext4(data: bytes) -> FSInfo | None:
    sb_offset = 1024
    if len(data) < sb_offset + 56:
        return None

    ext_magic = struct.unpack_from("<H", data, sb_offset + 56)[0]
    if ext_magic != 0xEF53:
        return None

    try:
        total_blocks = (
            struct.unpack_from("<Q", data, sb_offset + 4)[0]
            if len(data) >= sb_offset + 12
            else struct.unpack_from("<I", data, sb_offset + 4)[0]
        )
        block_size = 1024 << struct.unpack_from("<I", data, sb_offset + 24)[0]

        label_raw = data[sb_offset + 120 : sb_offset + 136]
        label = label_raw.decode("ascii", errors="replace").strip("\x00").strip()

        return FSInfo(
            fstype=FS_EXT234,
            label=label,
            sector_size=block_size,
            total_sectors=total_blocks * (block_size // 512) if block_size >= 512 else total_blocks,
            total_size=total_blocks * block_size,
            oem_id="ext2/3/4 (magic=0xEF53)",
        )
    except struct.error:
        return None
