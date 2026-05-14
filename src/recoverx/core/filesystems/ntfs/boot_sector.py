from __future__ import annotations

import struct

from .constants import NTFS_OEM_ID, NTFS_SIGNATURE
from .structures import NTFSBootSector


def parse_boot_sector(data: bytes) -> NTFSBootSector | None:
    if len(data) < 512:
        return None

    if data[3:11] != NTFS_OEM_ID:
        return None

    sig = struct.unpack_from("<H", data, 510)[0]
    signature_valid = sig == NTFS_SIGNATURE

    try:
        bytes_per_sector = struct.unpack_from("<H", data, 11)[0]
        sectors_per_cluster = data[13]
        total_sectors = struct.unpack_from("<Q", data, 40)[0]
        mft_cluster = struct.unpack_from("<Q", data, 48)[0]
        mft_mirror_cluster = struct.unpack_from("<Q", data, 56)[0]
        clusters_per_file_record_raw = data[64]
        if clusters_per_file_record_raw & 0x80:
            clusters_per_file_record = -(clusters_per_file_record_raw & 0x7F)
        else:
            clusters_per_file_record = clusters_per_file_record_raw
        clusters_per_index_block_raw = data[68]
        if clusters_per_index_block_raw & 0x80:
            clusters_per_index_block = -(clusters_per_index_block_raw & 0x7F)
        else:
            clusters_per_index_block = clusters_per_index_block_raw

        vol_serial_bytes = data[72:80]
        vol_serial = "-".join(
            [
                vol_serial_bytes[0:4].hex().upper(),
                vol_serial_bytes[4:6].hex().upper(),
                vol_serial_bytes[6:8].hex().upper(),
            ]
        )

        return NTFSBootSector(
            bytes_per_sector=bytes_per_sector,
            sectors_per_cluster=sectors_per_cluster,
            total_sectors=total_sectors,
            mft_cluster=mft_cluster,
            mft_mirror_cluster=mft_mirror_cluster,
            clusters_per_file_record=clusters_per_file_record,
            clusters_per_index_block=clusters_per_index_block,
            volume_serial=vol_serial,
            media_descriptor=data[21],
            signature_valid=signature_valid,
        )
    except (struct.error, IndexError):
        return None


def validate_boot_sector(bpb: NTFSBootSector) -> list[str]:
    issues: list[str] = []

    if bpb.bytes_per_sector not in (256, 512, 1024, 2048, 4096):
        issues.append(f"unusual bytes_per_sector: {bpb.bytes_per_sector}")

    if (
        bpb.sectors_per_cluster == 0
        or (bpb.sectors_per_cluster & (bpb.sectors_per_cluster - 1)) != 0
    ):
        issues.append(f"sectors_per_cluster not power of 2: {bpb.sectors_per_cluster}")

    if not bpb.signature_valid:
        issues.append("boot sector signature 0x55AA not found")

    if bpb.mft_cluster == 0:
        issues.append("mft_cluster is zero")

    if bpb.total_sectors == 0:
        issues.append("total_sectors is zero")

    return issues
