from __future__ import annotations

import os
import struct


def _make_bpb(
    bytes_per_sector: int = 512,
    sectors_per_cluster: int = 1,
    total_sectors: int = 65536,
    mft_cluster: int = 16,
    mft_mirror: int = 8,
    cpf_record: int = 0xF6,
) -> bytes:
    sector = bytearray(512)
    sector[0:3] = b"\xeb\x52\x90"
    sector[3:11] = b"NTFS    "
    struct.pack_into("<H", sector, 11, bytes_per_sector)
    sector[13] = sectors_per_cluster
    sector[21] = 0xF8
    struct.pack_into("<Q", sector, 40, total_sectors)
    struct.pack_into("<Q", sector, 48, mft_cluster)
    struct.pack_into("<Q", sector, 56, mft_mirror)
    sector[64] = cpf_record
    sector[68] = 0x01
    sector[66] = 0x29
    struct.pack_into("<Q", sector, 72, 0xA1B2C3D4E5F6)
    sector[510] = 0x55
    sector[511] = 0xAA
    return bytes(sector)


def _make_runlist_data(runs: list[tuple[int, int]]) -> bytes:
    runlist = bytearray()
    abs_lcn = 0
    for count, offset in runs:
        offset_delta = offset - abs_lcn
        abs_lcn = offset
        count_enc = _encode_vle(count)
        off_enc = _encode_vle_signed(offset_delta)
        header = (len(off_enc) << 4) | len(count_enc)
        runlist.append(header)
        runlist.extend(count_enc)
        runlist.extend(off_enc)
    runlist.append(0)
    return bytes(runlist)


def _encode_vle(value: int) -> bytes:
    result = bytearray()
    while value > 0:
        result.append(value & 0xFF)
        value >>= 8
    if not result:
        result.append(0)
    return bytes(result)


def _encode_vle_signed(value: int) -> bytes:
    if value == 0:
        return b"\x00"
    negative = value < 0
    if negative:
        value = -value
    result = bytearray()
    while value > 0:
        result.append(value & 0xFF)
        value >>= 8
    if negative:
        mask = 0xFF
        for i in range(len(result)):
            if i == len(result) - 1:
                result[i] = (~result[i] & mask) + 1
                result[i] = result[i] | 0x80
            else:
                result[i] = (~result[i]) & mask
    return bytes(result)


def _make_non_resident_data_attr(
    runs: list[tuple[int, int]],
    real_size: int,
    content: bytes,
) -> bytes:
    attr = bytearray(64)
    struct.pack_into("<I", attr, 0, 0x80)
    attr_size = 64 + len(content) + len(_make_runlist_data(runs))
    struct.pack_into("<I", attr, 4, attr_size)
    attr[8] = 0x81
    attr[9] = 0
    struct.pack_into("<H", attr, 10, 0)
    struct.pack_into("<H", attr, 12, 0)
    struct.pack_into("<H", attr, 14, 0)
    struct.pack_into("<Q", attr, 16, 0)
    vcn_end = sum(abs(c) for c, _ in runs) - 1
    struct.pack_into("<Q", attr, 24, vcn_end)
    struct.pack_into("<H", attr, 32, 64)
    struct.pack_into("<Q", attr, 40, sum(abs(c) for c, _ in runs) * 512)
    struct.pack_into("<Q", attr, 48, real_size)
    struct.pack_into("<Q", attr, 56, real_size)
    runlist_data = _make_runlist_data(runs)
    attr.extend(runlist_data)
    attr.extend(content)
    return bytes(attr)


def create_fragmented_image(tmpdir: str) -> str:
    """Create a simple NTFS image with fragmented non-resident data."""
    path = os.path.join(tmpdir, "ntfs_fragmented.bin")
    with open(path, "wb") as f:
        f.write(_make_bpb())
        f.seek(16 * 512)
        f.write(b"\x00" * (1024 * 10))
        f.seek(200 * 512)
        f.write(b"FRAGMENT_A" * 128)
        f.seek(400 * 512)
        f.write(b"FRAGMENT_B" * 128)
        f.seek(600 * 512)
        f.write(b"FRAGMENT_C" * 128)
        f.truncate()
    return path


def create_sparse_image(tmpdir: str) -> str:
    """Create a simple NTFS image with sparse regions."""
    path = os.path.join(tmpdir, "ntfs_sparse.bin")
    with open(path, "wb") as f:
        f.write(_make_bpb())
        f.seek(16 * 512)
        f.write(b"\x00" * (1024 * 10))
        f.seek(200 * 512)
        f.write(b"SPARSE_DATA" * 128)
        f.truncate()
    return path


def create_deleted_non_resident_image(tmpdir: str) -> str:
    """Create a simple NTFS image with a deleted non-resident file."""
    path = os.path.join(tmpdir, "ntfs_deleted_nr.bin")
    with open(path, "wb") as f:
        f.write(_make_bpb())
        f.seek(16 * 512)
        f.write(b"\x00" * (1024 * 10))
        f.seek(200 * 512)
        f.write(b"DELETED_NR_DATA" * 128)
        f.truncate()
    return path


def create_corrupted_runlist_image(tmpdir: str) -> str:
    """Create a simple NTFS image with a corrupted runlist."""
    path = os.path.join(tmpdir, "ntfs_corrupted_runs.bin")
    with open(path, "wb") as f:
        f.write(_make_bpb())
        f.seek(16 * 512)
        f.write(b"\x00" * (1024 * 10))
        f.seek(200 * 512)
        f.write(b"CORRUPTED" * 128)
        f.truncate()
    return path


def create_overlapping_runs_image(tmpdir: str) -> str:
    """Create image data for testing overlapping run detection."""
    path = os.path.join(tmpdir, "ntfs_overlapping_runs.bin")
    with open(path, "wb") as f:
        f.write(_make_bpb())
        f.seek(16 * 512)
        f.write(b"\x00" * (1024 * 10))
        f.seek(200 * 512)
        f.write(b"OVERLAP" * 128)
        f.seek(300 * 512)
        f.write(b"OVERLAP_B" * 128)
        f.truncate()
    return path
