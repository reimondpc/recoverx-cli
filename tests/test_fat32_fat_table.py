from __future__ import annotations

import struct

from recoverx.core.filesystems.fat32.fat_table import (
    get_next_cluster,
    is_bad_cluster,
    is_end_of_chain,
    is_free_cluster,
    is_valid_data_cluster,
    read_cluster_chain,
    read_cluster_data,
)
from recoverx.core.filesystems.fat32.structures import FAT32BootSector


class _FakeReader:
    def __init__(self, data: bytes, size: int | None = None):
        self._data = data
        self._size = size or len(data)

    @property
    def size(self) -> int:
        return self._size

    def read_at(self, offset: int, size: int) -> bytes:
        return self._data[offset : offset + size]


def _make_minimal_bpb() -> FAT32BootSector:
    return FAT32BootSector(
        bytes_per_sector=512,
        sectors_per_cluster=1,
        reserved_sectors=1,
        fat_count=2,
        fat_size_sectors=1,
        root_cluster=2,
        total_sectors=1024,
    )


class TestFATConstants:
    def test_end_of_chain(self):
        assert is_end_of_chain(0x0FFFFFF8)
        assert is_end_of_chain(0x0FFFFFFF)
        assert not is_end_of_chain(0x0FFFFFF7)

    def test_bad_cluster(self):
        assert is_bad_cluster(0x0FFFFFF7)
        assert not is_bad_cluster(0x0FFFFFF8)

    def test_free_cluster(self):
        assert is_free_cluster(0x00000000)
        assert not is_free_cluster(0x00000002)

    def test_valid_data_cluster(self):
        assert is_valid_data_cluster(2)
        assert is_valid_data_cluster(0x0FFFFFF6)
        assert not is_valid_data_cluster(0)
        assert not is_valid_data_cluster(1)
        assert not is_valid_data_cluster(0x0FFFFFF7)


class TestGetNextCluster:
    def _make_fat_image(self, entries: dict[int, int]) -> tuple[bytes, FAT32BootSector]:
        bpb = _make_minimal_bpb()
        fat_size = bpb.fat_size_sectors * bpb.bytes_per_sector
        fat = bytearray(fat_size)
        for cluster, value in entries.items():
            struct.pack_into("<I", fat, cluster * 4, value & 0x0FFFFFFF)

        data_offset = bpb.data_start
        total = data_offset + bpb.cluster_size * 10
        image = bytearray(total)
        image[bpb.fat_start : bpb.fat_start + len(fat)] = fat
        return bytes(image), bpb

    def test_simple_chain(self):
        image, bpb = self._make_fat_image({2: 3, 3: 0x0FFFFFFF})
        reader = _FakeReader(image)
        assert get_next_cluster(reader, bpb, 2) == 3
        assert is_end_of_chain(get_next_cluster(reader, bpb, 3))

    def test_eoc_returns_eoc(self):
        image, bpb = self._make_fat_image({2: 0x0FFFFFFF})
        reader = _FakeReader(image)
        assert is_end_of_chain(get_next_cluster(reader, bpb, 2))

    def test_bad_cluster(self):
        image, bpb = self._make_fat_image({2: 0x0FFFFFF7})
        reader = _FakeReader(image)
        assert is_bad_cluster(get_next_cluster(reader, bpb, 2))

    def test_out_of_range_returns_value(self):
        image, bpb = self._make_fat_image({})
        reader = _FakeReader(image)
        val = get_next_cluster(reader, bpb, 999)
        assert isinstance(val, int)


class TestReadClusterChain:
    def _make_chain_image(self, fat_entries: dict[int, int]) -> tuple[bytes, FAT32BootSector]:
        bpb = _make_minimal_bpb()
        fat_size = bpb.fat_size_sectors * bpb.bytes_per_sector
        fat = bytearray(fat_size)
        for cluster, value in fat_entries.items():
            struct.pack_into("<I", fat, cluster * 4, value & 0x0FFFFFFF)

        data_offset = bpb.data_start
        total = data_offset + bpb.cluster_size * 10
        image = bytearray(total)
        image[bpb.fat_start : bpb.fat_start + len(fat)] = fat
        return bytes(image), bpb

    def test_single_cluster_chain(self):
        image, bpb = self._make_chain_image({2: 0x0FFFFFFF})
        reader = _FakeReader(image)
        chain, status = read_cluster_chain(reader, bpb, 2)
        assert chain == [2]
        assert status == "ok"

    def test_multi_cluster_chain(self):
        image, bpb = self._make_chain_image({2: 3, 3: 4, 4: 0x0FFFFFFF})
        reader = _FakeReader(image)
        chain, status = read_cluster_chain(reader, bpb, 2)
        assert chain == [2, 3, 4]
        assert status == "ok"

    def test_free_start_cluster(self):
        image, bpb = self._make_chain_image({2: 0x00000000})
        reader = _FakeReader(image)
        chain, status = read_cluster_chain(reader, bpb, 2)
        assert chain == [2]
        assert status == "zero_next"

    def test_bad_cluster_detection(self):
        image, bpb = self._make_chain_image({2: 3, 3: 0x0FFFFFF7})
        reader = _FakeReader(image)
        chain, status = read_cluster_chain(reader, bpb, 2)
        assert chain == [2, 3]
        assert status == "bad_cluster"

    def test_start_cluster_below_2_returns_free(self):
        image, bpb = self._make_chain_image({})
        reader = _FakeReader(image)
        chain, status = read_cluster_chain(reader, bpb, 0)
        assert chain == []

    def test_chain_with_valid_data(self):
        bpb = _make_minimal_bpb()
        fat = bytearray(bpb.fat_size_sectors * bpb.bytes_per_sector)
        struct.pack_into("<I", fat, 2 * 4, 3)
        struct.pack_into("<I", fat, 3 * 4, 0x0FFFFFFF)

        data_offset = bpb.data_start
        total = data_offset + bpb.cluster_size * 10
        image = bytearray(total)
        image[bpb.fat_start : bpb.fat_start + len(fat)] = fat

        cluster2_data = b"CLUSTER2_DATA_" + b"X" * (bpb.cluster_size - 14)
        cluster3_data = b"CLUSTER3_DATA_" + b"Y" * (bpb.cluster_size - 14)
        image[data_offset : data_offset + len(cluster2_data)] = cluster2_data
        image[
            data_offset + bpb.cluster_size : data_offset + bpb.cluster_size + len(cluster3_data)
        ] = cluster3_data

        reader = _FakeReader(bytes(image))
        chain, status = read_cluster_chain(reader, bpb, 2)
        assert chain == [2, 3]
        assert status == "ok"


class TestReadClusterData:
    def test_read_data(self):
        bpb = FAT32BootSector(
            bytes_per_sector=512,
            sectors_per_cluster=1,
            reserved_sectors=1,
            fat_count=2,
            fat_size_sectors=1,
        )
        data_region = b"\xbb" * bpb.cluster_size * 5
        total_size = bpb.data_start + len(data_region)
        image = bytearray(total_size)
        image[bpb.data_start : bpb.data_start + len(data_region)] = data_region

        reader = _FakeReader(bytes(image), total_size)
        data = read_cluster_data(reader, bpb, 2)
        assert len(data) == bpb.cluster_size
        assert data == b"\xbb" * bpb.cluster_size

    def test_read_invalid_cluster(self):
        bpb = FAT32BootSector()
        reader = _FakeReader(b"")
        assert read_cluster_data(reader, bpb, 1) == b""

    def test_read_multiple_clusters(self):
        bpb = FAT32BootSector(
            bytes_per_sector=512,
            sectors_per_cluster=1,
            reserved_sectors=1,
            fat_count=2,
            fat_size_sectors=1,
        )
        pattern = b"\xcc" * bpb.cluster_size
        total_size = bpb.data_start + bpb.cluster_size * 5
        image = bytearray(total_size)
        for i in range(3):
            off = bpb.data_start + i * bpb.cluster_size
            image[off : off + bpb.cluster_size] = pattern

        reader = _FakeReader(bytes(image), total_size)
        for cluster in (2, 3, 4):
            data = read_cluster_data(reader, bpb, cluster)
            assert data == pattern
