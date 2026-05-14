from __future__ import annotations

import struct

from recoverx.core.filesystems.fat32.boot_sector import (
    parse_boot_sector,
    validate_boot_sector,
)
from recoverx.core.filesystems.fat32.structures import FAT32BootSector


def _make_bpb(
    bytes_per_sector: int = 512,
    sectors_per_cluster: int = 4,
    reserved_sectors: int = 32,
    fat_count: int = 2,
    fat_size: int = 32,
    root_cluster: int = 2,
    total_sectors: int = 51200,
    label: str = "TESTVOLUME",
) -> bytes:
    sector = bytearray(512)
    sector[0:3] = b"\xeb\x58\x90"
    sector[3:11] = b"RECOVERX"
    struct.pack_into("<H", sector, 11, bytes_per_sector)
    sector[13] = sectors_per_cluster
    struct.pack_into("<H", sector, 14, reserved_sectors)
    sector[16] = fat_count
    struct.pack_into("<H", sector, 17, 0)
    struct.pack_into("<H", sector, 19, 0)
    sector[21] = 0xF8
    struct.pack_into("<H", sector, 22, 0)
    struct.pack_into("<H", sector, 24, 63)
    struct.pack_into("<H", sector, 26, 255)
    struct.pack_into("<I", sector, 28, 0)
    struct.pack_into("<I", sector, 32, total_sectors)
    struct.pack_into("<I", sector, 36, fat_size)
    struct.pack_into("<H", sector, 40, 0)
    struct.pack_into("<H", sector, 42, 0)
    struct.pack_into("<I", sector, 44, root_cluster)
    struct.pack_into("<H", sector, 48, 1)
    struct.pack_into("<H", sector, 50, 6)
    sector[64] = 0x80
    sector[66] = 0x29
    struct.pack_into("<I", sector, 67, 0x12345678)
    label_bytes = label.encode("ascii").ljust(11)[:11]
    sector[71:82] = label_bytes
    sector[510] = 0x55
    sector[511] = 0xAA
    return bytes(sector)


class TestBootSectorParsing:
    def test_parse_valid_bpb(self):
        data = _make_bpb()
        bpb = parse_boot_sector(data)
        assert bpb is not None
        assert bpb.bytes_per_sector == 512
        assert bpb.sectors_per_cluster == 4
        assert bpb.cluster_size == 2048
        assert bpb.fat_count == 2
        assert bpb.fat_size_sectors == 32
        assert bpb.root_cluster == 2
        assert bpb.total_sectors == 51200
        assert bpb.signature_valid is True
        assert bpb.oem_id == "RECOVERX"

    def test_parse_volume_label(self):
        data = _make_bpb(label="MY_VOLUME")
        bpb = parse_boot_sector(data)
        assert bpb is not None
        assert "MY_VOLUME" in bpb.volume_label

    def test_parse_invalid_signature(self):
        data = _make_bpb()
        data = bytearray(data)
        data[510] = 0x00
        data[511] = 0x00
        bpb = parse_boot_sector(bytes(data))
        assert bpb is not None
        assert bpb.signature_valid is False

    def test_parse_too_short(self):
        assert parse_boot_sector(b"\x00" * 100) is None

    def test_parse_empty(self):
        assert parse_boot_sector(b"") is None

    def test_parse_zero_fat_size(self):
        data = _make_bpb(fat_size=0)
        assert parse_boot_sector(data) is None

    def test_bpb_computed_properties(self):
        bpb = FAT32BootSector(
            bytes_per_sector=512,
            sectors_per_cluster=8,
            reserved_sectors=32,
            fat_count=2,
            fat_size_sectors=64,
            root_cluster=2,
            total_sectors=1024000,
        )
        assert bpb.cluster_size == 4096
        assert bpb.fat_start == 16384
        assert bpb.data_start == 81920
        assert bpb.total_clusters > 0

    def test_bpb_to_dict(self):
        bpb = FAT32BootSector(volume_label="TEST", oem_id="TEST")
        d = bpb.to_dict()
        assert d["volume_label"] == "TEST"
        assert d["oem_id"] == "TEST"
        assert "fat_start_offset" in d


class TestBootSectorValidation:
    def test_valid_bpb_no_issues(self):
        bpb = FAT32BootSector(
            bytes_per_sector=512,
            sectors_per_cluster=1,
            reserved_sectors=32,
            fat_count=2,
            fat_size_sectors=32,
            root_cluster=2,
            total_sectors=2000000,
            signature_valid=True,
        )
        issues = validate_boot_sector(bpb)
        assert len(issues) == 0

    def test_invalid_sectors_per_cluster(self):
        bpb = FAT32BootSector(bytes_per_sector=512, sectors_per_cluster=3)
        issues = validate_boot_sector(bpb)
        assert any("not power of 2" in i for i in issues)

    def test_zero_fat_size(self):
        bpb = FAT32BootSector(fat_size_sectors=0)
        issues = validate_boot_sector(bpb)
        assert any("zero" in i.lower() for i in issues)

    def test_invalid_root_cluster(self):
        bpb = FAT32BootSector(root_cluster=0)
        issues = validate_boot_sector(bpb)
        assert any("invalid root_cluster" in i for i in issues)

    def test_invalid_signature(self):
        bpb = FAT32BootSector(signature_valid=False)
        issues = validate_boot_sector(bpb)
        assert any("signature" in i for i in issues)

    def test_unusual_bytes_per_sector(self):
        bpb = FAT32BootSector(bytes_per_sector=200)
        issues = validate_boot_sector(bpb)
        assert any("unusual" in i for i in issues)
