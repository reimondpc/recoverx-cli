from __future__ import annotations

import struct

from recoverx.core.filesystems.fat32.recovery import FAT32Recovery
from recoverx.core.filesystems.fat32.structures import (
    FAT32BootSector,
    FATAttributes,
    FATDirEntry,
)


class _FakeReader:
    def __init__(self, data: bytes, size: int | None = None):
        self._data = data
        self._size = size or len(data)

    @property
    def size(self) -> int:
        return self._size

    def read_at(self, offset: int, size: int) -> bytes:
        return self._data[offset : offset + size]


def _make_fat32_image(
    file_clusters: list[int],
    file_data: bytes,
    fat_chain_values: list[int],
) -> bytes:
    bpb = FAT32BootSector(
        bytes_per_sector=512,
        sectors_per_cluster=1,
        reserved_sectors=32,
        fat_count=2,
        fat_size_sectors=8,
        root_cluster=2,
        total_sectors=102400,
    )

    fat_size = bpb.fat_size_sectors * bpb.bytes_per_sector
    data_offset = bpb.data_start
    image_size = data_offset + 512 * 64
    image = bytearray(image_size)

    fat = bytearray(fat_size)
    for i, next_cluster in enumerate(fat_chain_values):
        struct.pack_into("<I", fat, (i + 2) * 4, next_cluster & 0x0FFFFFFF)

    for fat_idx in range(bpb.fat_count):
        offset = bpb.fat_start + fat_idx * fat_size
        image[offset : offset + len(fat)] = fat

    for i, cluster in enumerate(file_clusters):
        cluster_off = data_offset + (cluster - 2) * bpb.cluster_size
        chunk = file_data[i * bpb.cluster_size : (i + 1) * bpb.cluster_size]
        image[cluster_off : cluster_off + len(chunk)] = chunk

    return bytes(image), bpb


class TestFAT32Recovery:
    def test_recover_single_cluster_file(self):
        file_data = b"Hello, FAT32 Recovery!" * 10
        fat_chain = [0x0FFFFFFF]
        image, bpb = _make_fat32_image([3], file_data, fat_chain)

        reader = _FakeReader(image, len(image))
        rec = FAT32Recovery(reader, bpb)

        entry = FATDirEntry(
            short_name="TEST.TXT",
            extension="TXT",
            start_cluster=3,
            file_size=len(file_data),
            deleted=True,
            attributes=FATAttributes(archive=True),
        )

        result = rec.recover_deleted_file(entry)
        assert result.recovery_status == "recovered"
        assert result.data == file_data
        assert len(result.sha256) == 64

    def test_recover_multi_cluster_file(self):
        bpb_std = FAT32BootSector(
            bytes_per_sector=512,
            sectors_per_cluster=1,
            reserved_sectors=1,
            fat_count=2,
            fat_size_sectors=1,
            root_cluster=2,
            total_sectors=10240,
        )
        cluster_size = bpb_std.cluster_size
        data_size = int(cluster_size * 2)
        file_data = b"X" * data_size

        fat_data = bytearray(bpb_std.fat_size_sectors * bpb_std.bytes_per_sector)
        struct.pack_into("<I", fat_data, 2 * 4, 3)
        struct.pack_into("<I", fat_data, 3 * 4, 4)
        struct.pack_into("<I", fat_data, 4 * 4, 0x0FFFFFFF)

        data_offset = bpb_std.data_start
        image_size = data_offset + cluster_size * 10
        image = bytearray(image_size)

        for fat_idx in range(bpb_std.fat_count):
            offset = bpb_std.fat_start + fat_idx * len(fat_data)
            image[offset : offset + len(fat_data)] = fat_data

        for i in range(3):
            cluster_off = data_offset + (2 + i) * cluster_size
            chunk = file_data[i * cluster_size : (i + 1) * cluster_size]
            image[cluster_off : cluster_off + len(chunk)] = chunk

        reader = _FakeReader(bytes(image), len(image))
        rec = FAT32Recovery(reader, bpb_std)

        entry = FATDirEntry(
            short_name="BIG.DAT",
            extension="DAT",
            start_cluster=2,
            file_size=len(file_data),
            deleted=True,
        )

        result = rec.recover_deleted_file(entry)
        assert (
            result.recovery_status == "recovered"
        ), f"status={result.recovery_status}, notes={result.recovery_notes}"
        assert len(result.data) == len(file_data)

    def test_no_start_cluster(self):
        bpb = FAT32BootSector(
            bytes_per_sector=512,
            reserved_sectors=32,
            fat_size_sectors=8,
        )
        reader = _FakeReader(b"", 1024)
        rec = FAT32Recovery(reader, bpb)

        entry = FATDirEntry(short_name="EMPTY.TXT", start_cluster=0, file_size=0)
        result = rec.recover_deleted_file(entry)
        assert result.recovery_status == "no_start_cluster"

    def test_directory_skipped(self):
        bpb = FAT32BootSector(
            bytes_per_sector=512,
            reserved_sectors=32,
            fat_size_sectors=8,
        )
        reader = _FakeReader(b"", 1024)
        rec = FAT32Recovery(reader, bpb)

        entry = FATDirEntry(
            short_name="DIR",
            start_cluster=3,
            file_size=0,
            is_directory=True,
            attributes=FATAttributes(subdirectory=True),
        )
        result = rec.recover_deleted_file(entry)
        assert result.recovery_status == "skipped_directory"

    def test_save_recovered(self):
        import tempfile

        bpb = FAT32BootSector()
        reader = _FakeReader(b"", 1024)
        rec = FAT32Recovery(reader, bpb)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = rec.recover_deleted_file(
                FATDirEntry(
                    short_name="SAVED.TXT",
                    extension="TXT",
                    start_cluster=3,
                    file_size=5,
                    deleted=True,
                )
            )
            result.data = b"HELLO"
            saved = rec.save_recovered(result, output_dir=tmpdir)
            assert saved is not None
            assert "DELETED" in saved
