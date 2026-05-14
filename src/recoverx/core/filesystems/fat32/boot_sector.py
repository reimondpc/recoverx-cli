from __future__ import annotations

import struct

from .structures import FAT32BootSector

FAT32_SIGNATURE = 0xAA55
FAT32_MIN_CLUSTERS = 65525
FAT32_MIN_SECTORS = 65536


def parse_boot_sector(data: bytes) -> FAT32BootSector | None:
    if len(data) < 512:
        return None

    sig = struct.unpack_from("<H", data, 510)[0]
    signature_valid = sig == FAT32_SIGNATURE

    try:
        bytes_per_sector = struct.unpack_from("<H", data, 11)[0]
        sectors_per_cluster = data[13]
        reserved_sectors = struct.unpack_from("<H", data, 14)[0]
        fat_count = data[16]
        total_sectors_16 = struct.unpack_from("<H", data, 19)[0]
        media_descriptor = data[21]
        hidden_sectors = struct.unpack_from("<I", data, 28)[0]
        total_sectors_32 = struct.unpack_from("<I", data, 32)[0]

        sectors_per_fat_32 = struct.unpack_from("<I", data, 36)[0]
        mirroring_flags = struct.unpack_from("<H", data, 40)[0]
        fs_version = struct.unpack_from("<H", data, 42)[0]
        root_cluster = struct.unpack_from("<I", data, 44)[0]
        fs_info_sector = struct.unpack_from("<H", data, 48)[0]
        backup_boot_sector = struct.unpack_from("<H", data, 50)[0]

        total_sectors = total_sectors_32 if total_sectors_32 != 0 else total_sectors_16

        vol_id_raw = data[67:71]
        volume_id = "-".join(
            [
                vol_id_raw[0:2].hex().upper(),
                vol_id_raw[2:4].hex().upper(),
            ]
        )

        label_raw = data[71:82]
        volume_label = label_raw.decode("ascii", errors="replace").strip()

        oem_raw = data[3:11]
        oem_id = oem_raw.decode("ascii", errors="replace").strip()

        active_fat = mirroring_flags & 0x0F
        mirroring_enabled = (mirroring_flags & 0x80) == 0

        if sectors_per_fat_32 == 0:
            return None

        return FAT32BootSector(
            bytes_per_sector=bytes_per_sector,
            sectors_per_cluster=sectors_per_cluster,
            reserved_sectors=reserved_sectors,
            fat_count=fat_count,
            fat_size_sectors=sectors_per_fat_32,
            root_cluster=root_cluster if root_cluster != 0 else 2,
            total_sectors=total_sectors,
            fs_info_sector=fs_info_sector,
            backup_boot_sector=backup_boot_sector,
            media_descriptor=media_descriptor,
            volume_id=volume_id,
            volume_label=volume_label,
            oem_id=oem_id,
            active_fat=active_fat,
            mirrroring_enabled=mirroring_enabled,
            fs_version=fs_version,
            signature_valid=signature_valid,
            hidden_sectors=hidden_sectors,
        )

    except (struct.error, IndexError):
        return None


def validate_boot_sector(bpb: FAT32BootSector) -> list[str]:
    issues: list[str] = []

    if bpb.bytes_per_sector not in (512, 1024, 2048, 4096):
        issues.append(f"unusual bytes_per_sector: {bpb.bytes_per_sector}")

    if (
        bpb.sectors_per_cluster == 0
        or (bpb.sectors_per_cluster & (bpb.sectors_per_cluster - 1)) != 0
    ):
        issues.append(f"sectors_per_cluster not power of 2: {bpb.sectors_per_cluster}")

    if bpb.fat_count < 1 or bpb.fat_count > 2:
        issues.append(f"unusual fat_count: {bpb.fat_count}")

    if bpb.fat_size_sectors == 0:
        issues.append("fat_size is zero")

    if bpb.root_cluster < 2:
        issues.append(f"invalid root_cluster: {bpb.root_cluster}")

    if not bpb.signature_valid:
        issues.append("boot sector signature 0x55AA not found")

    total_clusters = bpb.total_clusters
    if total_clusters < FAT32_MIN_CLUSTERS:
        issues.append(f"too few clusters ({total_clusters}) for FAT32, looks like FAT16/FAT12")

    return issues
