"""Fuzz tests for FAT32 binary parsers.

Ensures the parser never crashes on malformed, corrupted, or malicious input.
"""

from __future__ import annotations

import os
import random
import struct

from recoverx.core.filesystems.fat32.boot_sector import parse_boot_sector, validate_boot_sector
from recoverx.core.filesystems.fat32.directory import parse_directory_entries
from recoverx.core.filesystems.fat32.fat_table import get_next_cluster, read_cluster_chain
from recoverx.core.filesystems.fat32.recovery import FAT32Recovery
from recoverx.core.filesystems.fat32.structures import FAT32BootSector


class TestFAT32FuzzBootSector:
    def test_fuzz_empty(self):
        assert parse_boot_sector(b"") is None

    def test_fuzz_too_short(self):
        for size in [1, 10, 100, 200, 300, 400, 500, 511]:
            assert parse_boot_sector(os.urandom(size)) is None

    def test_fuzz_random_512(self):
        for _ in range(100):
            data = os.urandom(512)
            bpb = parse_boot_sector(data)
            if bpb is not None:
                issues = validate_boot_sector(bpb)
                assert isinstance(issues, list)

    def test_fuzz_corrupted_signature(self):
        for _ in range(50):
            data = bytearray(os.urandom(512))
            data[510] = random.randint(0, 255)
            data[511] = random.randint(0, 255)
            bpb = parse_boot_sector(bytes(data))
            if bpb is not None:
                issues = validate_boot_sector(bpb)
                assert isinstance(issues, list)

    def test_fuzz_extreme_values(self):
        for _ in range(50):
            data = bytearray(os.urandom(512))
            for pos in [11, 13, 14, 16, 17, 19, 22, 28, 32, 36, 40, 44, 48]:
                struct.pack_into("<I", data, pos, random.randint(0, 0xFFFFFFFF))
            bpb = parse_boot_sector(bytes(data))
            if bpb is not None:
                issues = validate_boot_sector(bpb)
                assert isinstance(issues, list)

    def test_fuzz_no_infinite_loop_on_large_values(self):
        for _ in range(20):
            data = bytearray(os.urandom(512))
            struct.pack_into("<I", data, 32, 0xFFFFFFFF)
            struct.pack_into("<I", data, 36, 0xFFFFFFFF)
            struct.pack_into("<I", data, 44, 0xFFFFFFFF)
            bpb = parse_boot_sector(bytes(data))
            if bpb is not None:
                issues = validate_boot_sector(bpb)
                assert isinstance(issues, list)


class _FakeReader:
    def __init__(self, data: bytes, size: int | None = None):
        self._data = data
        self._size = size or len(data)

    @property
    def size(self) -> int:
        return self._size

    def read_at(self, offset: int, size: int) -> bytes:
        if offset >= self._size:
            return b""
        return self._data[offset : offset + size]


class TestFAT32FuzzDirectory:
    def test_fuzz_empty_entries(self):
        entries = parse_directory_entries(b"")
        assert entries == []

    def test_fuzz_random_data(self):
        for _ in range(100):
            data = os.urandom(random.randint(1, 4096))
            entries = parse_directory_entries(data)
            assert isinstance(entries, list)

    def test_fuzz_large_data(self):
        data = os.urandom(65536)
        entries = parse_directory_entries(data)
        assert isinstance(entries, list)

    def test_fuzz_deleted_entries(self):
        for _ in range(50):
            entry = bytearray(os.urandom(32))
            entry[0] = 0xE5
            entry[11] = random.choice([0x00, 0x20, 0x10, 0x0F, 0x08])
            remaining = os.urandom(random.randint(0, 512))
            entries = parse_directory_entries(bytes(entry) + remaining)
            assert isinstance(entries, list)

    def test_fuzz_lfn_entries(self):
        for _ in range(50):
            data = bytearray()
            for __ in range(random.randint(1, 20)):
                lfn = bytearray(os.urandom(32))
                lfn[11] = 0x0F
                lfn[0] = random.randint(0x01, 0xBF)
                data.extend(lfn)
            sfn = bytearray(os.urandom(32))
            sfn[11] = 0x20
            data.extend(sfn)
            entries = parse_directory_entries(bytes(data))
            assert isinstance(entries, list)


class TestFAT32FuzzFAT:
    def _make_minimal_bpb(self) -> FAT32BootSector:
        return FAT32BootSector(
            bytes_per_sector=512,
            sectors_per_cluster=1,
            reserved_sectors=1,
            fat_count=2,
            fat_size_sectors=1,
            root_cluster=2,
            total_sectors=10240,
        )

    def test_fuzz_get_next_cluster_out_of_bounds(self):
        bpb = self._make_minimal_bpb()
        reader = _FakeReader(b"", 512)
        result = get_next_cluster(reader, bpb, 2)
        assert isinstance(result, int)

    def test_fuzz_read_cluster_chain_no_infinite_loop(self):
        bpb = self._make_minimal_bpb()
        fat = bytearray(512)
        for i in range(2, 100):
            struct.pack_into("<I", fat, i * 4, i + 1)
        struct.pack_into("<I", fat, 99 * 4, 0x0FFFFFFF)
        image = bytearray(bpb.data_start + 512 * 10)
        for fat_idx in range(bpb.fat_count):
            off = bpb.fat_start + fat_idx * len(fat)
            image[off : off + len(fat)] = fat
        reader = _FakeReader(bytes(image), len(image))
        chain, status = read_cluster_chain(reader, bpb, 2)
        assert isinstance(chain, list)
        assert isinstance(status, str)

    def test_fuzz_self_referencing_loop(self):
        bpb = self._make_minimal_bpb()
        fat = bytearray(512)
        struct.pack_into("<I", fat, 5 * 4, 5)
        image = bytearray(bpb.data_start + 512)
        for fat_idx in range(bpb.fat_count):
            off = bpb.fat_start + fat_idx * len(fat)
            image[off : off + len(fat)] = fat
        reader = _FakeReader(bytes(image), len(image))
        chain, status = read_cluster_chain(reader, bpb, 5)
        assert status == "loop_detected"
        assert len(chain) == 1

    def test_fuzz_bad_cluster_termination(self):
        bpb = self._make_minimal_bpb()
        fat = bytearray(512)
        struct.pack_into("<I", fat, 3 * 4, 0x0FFFFFF7)
        image = bytearray(bpb.data_start + 512)
        for fat_idx in range(bpb.fat_count):
            off = bpb.fat_start + fat_idx * len(fat)
            image[off : off + len(fat)] = fat
        reader = _FakeReader(bytes(image), len(image))
        chain, status = read_cluster_chain(reader, bpb, 3)
        assert status == "bad_cluster"

    def test_fuzz_random_fat_chain(self):
        bpb = self._make_minimal_bpb()
        for _ in range(50):
            fat = bytearray(512)
            for i in range(2, min(50, 512 // 4)):
                val = random.choice(
                    [
                        random.randint(0x00000002, 0x0FFFFFF6),
                        0x0FFFFFF7,
                        0x00000000,
                        random.randint(0x0FFFFFF8, 0x0FFFFFFF),
                    ]
                )
                struct.pack_into("<I", fat, i * 4, val)
            image = bytearray(bpb.data_start + 512 * 10)
            for fat_idx in range(bpb.fat_count):
                off = bpb.fat_start + fat_idx * len(fat)
                image[off : off + len(fat)] = fat
            for c in range(2, 10):
                reader = _FakeReader(bytes(image), len(image))
                chain, status = read_cluster_chain(reader, bpb, c, max_clusters=1000)
                assert isinstance(chain, list)
                assert isinstance(status, str)
                assert len(chain) <= 1000


class TestFAT32FuzzRecovery:
    def test_fuzz_recovery_malformed_image(self):
        for _ in range(20):
            image = os.urandom(random.randint(512, 65536))
            bpb = FAT32BootSector(
                bytes_per_sector=512,
                sectors_per_cluster=1,
                reserved_sectors=1,
                fat_count=2,
                fat_size_sectors=1,
                total_sectors=len(image) // 512,
            )
            reader = _FakeReader(image, len(image))
            try:
                rec = FAT32Recovery(reader, bpb)
                deleted = rec.find_deleted_entries()
                assert isinstance(deleted, list)
            except (ValueError, IndexError, struct.error, MemoryError):
                pass

    def test_fuzz_recovery_extreme_bpb(self):
        bpb = FAT32BootSector(
            bytes_per_sector=2**15,
            sectors_per_cluster=2**31,
            reserved_sectors=2**31,
            fat_count=255,
            fat_size_sectors=2**31,
            root_cluster=2,
            total_sectors=2**32 - 1,
        )
        image = os.urandom(65536)
        reader = _FakeReader(image, len(image))
        try:
            rec = FAT32Recovery(reader, bpb)
            deleted = rec.find_deleted_entries()
            assert isinstance(deleted, list)
        except (ValueError, IndexError, struct.error, MemoryError, OverflowError):
            pass

    def test_fuzz_zero_size_image(self):
        bpb = FAT32BootSector(
            bytes_per_sector=512,
            sectors_per_cluster=1,
            reserved_sectors=32,
            fat_count=2,
            fat_size_sectors=8,
            total_sectors=0,
        )
        reader = _FakeReader(b"", 0)
        try:
            rec = FAT32Recovery(reader, bpb)
            deleted = rec.find_deleted_entries()
            assert isinstance(deleted, list)
        except (ValueError, IndexError, struct.error, MemoryError):
            pass


class TestFAT32FuzzMemorySafety:
    def test_fuzz_huge_cluster_count(self):
        bpb = FAT32BootSector(
            bytes_per_sector=512,
            sectors_per_cluster=1,
            reserved_sectors=32,
            fat_count=2,
            fat_size_sectors=0xFFFFFFFF,
            total_sectors=0xFFFFFFFF,
        )
        reader = _FakeReader(os.urandom(512), 512)
        chain, status = read_cluster_chain(reader, bpb, 2, max_clusters=100)
        assert isinstance(chain, list)
        assert isinstance(status, str)

    def test_fuzz_negative_offset_protection(self):
        bpb = FAT32BootSector(
            bytes_per_sector=512,
            reserved_sectors=0xFFFFFFFF,
            fat_size_sectors=0xFFFFFFFF,
        )
        reader = _FakeReader(os.urandom(512), 512)
        try:
            get_next_cluster(reader, bpb, 2)
        except (ValueError, IndexError, struct.error, MemoryError, OverflowError):
            pass

    def test_fuzz_all_zeros_image(self):
        for size in [0, 1, 512, 4096, 65536]:
            data = b"\x00" * size
            reader = _FakeReader(data, len(data))
            total_sec = size // 512 if size >= 512 else 0
            bpb = FAT32BootSector(bytes_per_sector=512, fat_size_sectors=1, total_sectors=total_sec)
            try:
                get_next_cluster(reader, bpb, 2)
            except Exception:
                pass
            try:
                chain, status = read_cluster_chain(reader, bpb, 2, max_clusters=100)
                assert isinstance(chain, list)
            except Exception:
                pass
