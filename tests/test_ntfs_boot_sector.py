from __future__ import annotations

import struct

from recoverx.core.filesystems.ntfs.boot_sector import parse_boot_sector, validate_boot_sector
from recoverx.core.filesystems.ntfs.structures import NTFSBootSector


def _make_bpb(
    bytes_per_sector: int = 512,
    sectors_per_cluster: int = 8,
    total_sectors: int = 256000,
    mft_cluster: int = 32768,
    mft_mirror: int = 4,
    cpf_record: int = 0xF6,
    label: str = "NTFSVOLUME",
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
    vol_id = 0xA1B2C3D4E5F6
    struct.pack_into("<Q", sector, 72, vol_id)
    label_bytes = label.encode("ascii").ljust(11)[:11]
    sector[71:82] = label_bytes
    sector[510] = 0x55
    sector[511] = 0xAA
    return bytes(sector)


class TestNTFSBootSectorParsing:
    def test_parse_valid_bpb(self):
        data = _make_bpb()
        bpb = parse_boot_sector(data)
        assert bpb is not None
        assert bpb.bytes_per_sector == 512
        assert bpb.sectors_per_cluster == 8
        assert bpb.cluster_size == 4096
        assert bpb.total_sectors == 256000
        assert bpb.mft_cluster == 32768
        assert bpb.signature_valid is True
        assert bpb.oem_id == "NTFS"

    def test_parse_too_short(self):
        assert parse_boot_sector(b"\x00" * 100) is None

    def test_parse_empty(self):
        assert parse_boot_sector(b"") is None

    def test_parse_non_ntfs(self):
        data = bytearray(512)
        data[3:11] = b"FAT32   "
        data[510] = 0x55
        data[511] = 0xAA
        assert parse_boot_sector(bytes(data)) is None

    def test_parse_invalid_signature(self):
        data = _make_bpb()
        data = bytearray(data)
        data[510] = 0x00
        data[511] = 0x00
        bpb = parse_boot_sector(bytes(data))
        assert bpb is not None
        assert bpb.signature_valid is False

    def test_bpb_computed_properties(self):
        bpb = NTFSBootSector(
            bytes_per_sector=512,
            sectors_per_cluster=8,
            mft_cluster=50000,
            total_sectors=512000,
        )
        assert bpb.cluster_size == 4096
        assert bpb.mft_byte_offset == 50000 * 4096
        assert bpb.total_size == 512000 * 512

    def test_bpb_to_dict(self):
        bpb = NTFSBootSector(volume_serial="ABCD-1234", oem_id="NTFS")
        d = bpb.to_dict()
        assert d["volume_serial"] == "ABCD-1234"
        assert d["oem_id"] == "NTFS"

    def test_bytes_per_file_record_positive(self):
        bpb = NTFSBootSector(
            clusters_per_file_record=1, sectors_per_cluster=8, bytes_per_sector=512
        )
        assert bpb.bytes_per_file_record == 4096 * 2

    def test_bytes_per_file_record_negative(self):
        bpb = NTFSBootSector(
            clusters_per_file_record=-1, sectors_per_cluster=8, bytes_per_sector=512
        )
        assert bpb.bytes_per_file_record == 4096 // 2


class TestNTFSBootSectorValidation:
    def test_valid_bpb_no_issues(self):
        bpb = NTFSBootSector(
            bytes_per_sector=512,
            sectors_per_cluster=8,
            total_sectors=256000,
            mft_cluster=32768,
            signature_valid=True,
        )
        issues = validate_boot_sector(bpb)
        assert len(issues) == 0

    def test_invalid_sectors_per_cluster(self):
        bpb = NTFSBootSector(bytes_per_sector=512, sectors_per_cluster=3)
        issues = validate_boot_sector(bpb)
        assert any("not power of 2" in i for i in issues)

    def test_invalid_signature(self):
        bpb = NTFSBootSector(signature_valid=False)
        issues = validate_boot_sector(bpb)
        assert any("signature" in i for i in issues)

    def test_zero_mft_cluster(self):
        bpb = NTFSBootSector(mft_cluster=0)
        issues = validate_boot_sector(bpb)
        assert any("mft_cluster is zero" in i for i in issues)
