"""Fuzz tests for NTFS binary parsers.

Ensures the NTFS parser never crashes on malformed or malicious input.
"""

from __future__ import annotations

import os
import random
import struct

from recoverx.core.filesystems.ntfs.boot_sector import parse_boot_sector, validate_boot_sector
from recoverx.core.filesystems.ntfs.attributes import (
    parse_attributes, parse_attribute_header, parse_runlist,
)
from recoverx.core.filesystems.ntfs.mft import (
    parse_mft_record, parse_mft_record_header, apply_fixups,
)
from recoverx.core.filesystems.ntfs.structures import NTFSBootSector


class TestNTFSFuzzBootSector:
    def test_fuzz_empty(self):
        assert parse_boot_sector(b"") is None

    def test_fuzz_too_short(self):
        for size in [1, 10, 100, 200, 300, 400, 500, 511]:
            data = bytearray(size)
            if size > 3:
                data[3:11] = b"NTFS    "
            assert parse_boot_sector(bytes(data)) is None

    def test_fuzz_random_512(self):
        for _ in range(50):
            data = bytearray(os.urandom(512))
            data[3:11] = b"NTFS    "
            bpb = parse_boot_sector(bytes(data))
            if bpb is not None:
                issues = validate_boot_sector(bpb)
                assert isinstance(issues, list)

    def test_fuzz_corrupted_signature(self):
        for _ in range(30):
            data = bytearray(os.urandom(512))
            data[3:11] = b"NTFS    "
            data[510] = random.randint(0, 255)
            data[511] = random.randint(0, 255)
            bpb = parse_boot_sector(bytes(data))
            if bpb is not None:
                issues = validate_boot_sector(bpb)
                assert isinstance(issues, list)

    def test_fuzz_extreme_values(self):
        for _ in range(30):
            data = bytearray(os.urandom(512))
            data[3:11] = b"NTFS    "
            for pos in [11, 13, 40, 48, 56, 64, 68]:
                struct.pack_into("<Q", data, pos, random.randint(0, 0xFFFFFFFFFFFFFFFF))
            bpb = parse_boot_sector(bytes(data))
            if bpb is not None:
                issues = validate_boot_sector(bpb)
                assert isinstance(issues, list)


class TestNTFSFuzzMFT:
    def test_fuzz_empty(self):
        assert parse_mft_record(b"") is None

    def test_fuzz_random_data(self):
        for _ in range(50):
            data = os.urandom(random.randint(48, 4096))
            record = parse_mft_record(data)
            if record is not None:
                assert isinstance(record.header.flags, int)

    def test_fuzz_header_no_file_sig(self):
        for _ in range(20):
            data = os.urandom(1024)
            assert parse_mft_record_header(data) is None

    def test_fuzz_file_sig_wrong_offset(self):
        for _ in range(20):
            data = bytearray(os.urandom(1024))
            data[0:4] = b"FILE"
            header = parse_mft_record_header(bytes(data))
            if header is not None:
                assert isinstance(header.flags, int)

    def test_fuzz_fixups(self):
        for _ in range(30):
            data = bytearray(os.urandom(1024))
            data[0:4] = b"FILE"
            struct.pack_into("<H", data, 4, random.randint(0, 512))
            struct.pack_into("<H", data, 6, random.randint(0, 10))
            header = parse_mft_record_header(bytes(data))
            if header is not None:
                applied = apply_fixups(bytes(data), header)
                assert isinstance(applied, bytes)

    def test_fuzz_extreme_header_values(self):
        for _ in range(30):
            data = bytearray(os.urandom(1024))
            data[0:4] = b"FILE"
            for pos in [4, 6, 8, 16, 18, 20, 22, 24, 28, 44]:
                struct.pack_into("<I", data, pos, random.randint(0, 0xFFFFFFFF))
            header = parse_mft_record_header(bytes(data))
            if header is not None:
                assert isinstance(header.flags, int)


class TestNTFSFuzzAttributes:
    def test_fuzz_empty(self):
        assert parse_attributes(b"") == []

    def test_fuzz_random_data(self):
        for _ in range(50):
            data = os.urandom(random.randint(0, 4096))
            attrs = parse_attributes(data)
            assert isinstance(attrs, list)

    def test_fuzz_runlist(self):
        for _ in range(50):
            data = os.urandom(random.randint(0, 512))
            runs = parse_runlist(data, 0)
            assert isinstance(runs, list)

    def test_fuzz_single_attr_random(self):
        for _ in range(50):
            data = bytearray(os.urandom(random.randint(16, 256)))
            data[0:4] = struct.pack("<I", random.choice([0x10, 0x30, 0x80, 0x90]))
            attr = parse_attribute_header(data, 0)
            if attr is not None:
                assert isinstance(attr.attr_type, int)

    def test_fuzz_terminator(self):
        data = b"\xff" * 16
        assert parse_attribute_header(data, 0) is None

    def test_fuzz_large_data_array(self):
        for _ in range(20):
            attrs_data = bytearray()
            for __ in range(10):
                chunk = bytearray(os.urandom(random.randint(16, 200)))
                chunk[0:4] = struct.pack("<I", random.choice([0x10, 0x30, 0x80]))
                chunk[4:8] = struct.pack("<I", len(chunk))
                attrs_data.extend(chunk)
            attrs_data.extend(b"\xff" * 16)
            attrs = parse_attributes(bytes(attrs_data))
            assert isinstance(attrs, list)

    def test_fuzz_zero_length(self):
        data = struct.pack("<II", 0x10, 0) + os.urandom(100)
        attrs = parse_attributes(data)
        assert isinstance(attrs, list)


class TestNTFSFuzzRecovery:
    def test_fuzz_extreme_bpb(self):
        bpb = NTFSBootSector(
            bytes_per_sector=2**15,
            sectors_per_cluster=2**31,
            mft_cluster=2**63,
            clusters_per_file_record=-10,
            total_sectors=2**63 - 1,
        )
        from recoverx.core.filesystems.ntfs.recovery import NTFSRecovery

        class _FakeReader:
            def __init__(self):
                self.size = 65536

            def read_at(self, offset, size):
                return os.urandom(min(size, 4096))

        reader = _FakeReader()
        try:
            rec = NTFSRecovery(reader, bpb)
            records = rec.walk_mft(max_records=5)
            assert isinstance(records, list)
        except (ValueError, IndexError, struct.error, MemoryError, OverflowError):
            pass

    def test_fuzz_zero_image(self):
        bpb = NTFSBootSector(bytes_per_sector=512, clusters_per_file_record=0)
        from recoverx.core.filesystems.ntfs.recovery import NTFSRecovery

        class _FakeReader:
            def __init__(self):
                self.size = 0

            def read_at(self, offset, size):
                return b""

        reader = _FakeReader()
        try:
            rec = NTFSRecovery(reader, bpb)
            records = rec.walk_mft(max_records=5)
            assert isinstance(records, list)
        except (ValueError, IndexError, struct.error, MemoryError):
            pass
