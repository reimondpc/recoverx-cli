from __future__ import annotations

import logging
import struct

from recoverx.core.utils.raw_reader import RawReader

from .structures import FAT32BootSector

logger = logging.getLogger("recoverx")

RESERVED_CLUSTER = 0x00000001
EOC_MIN = 0x0FFFFFF8
EOC_MAX = 0x0FFFFFFF
BAD_CLUSTER = 0x0FFFFFF7
FREE_CLUSTER = 0x00000000


def is_end_of_chain(value: int) -> bool:
    return EOC_MIN <= value <= EOC_MAX


def is_bad_cluster(value: int) -> bool:
    return value == BAD_CLUSTER


def is_free_cluster(value: int) -> bool:
    return value == FREE_CLUSTER


def is_valid_data_cluster(value: int) -> bool:
    return 0x00000002 <= value <= 0x0FFFFFF6


def get_next_cluster(reader: RawReader, bpb: FAT32BootSector, cluster: int) -> int:
    fat_offset = bpb.fat_start + cluster * 4
    if fat_offset + 4 > reader.size:
        return EOC_MAX
    data = reader.read_at(fat_offset, 4)
    if len(data) < 4:
        return EOC_MAX
    return struct.unpack_from("<I", data)[0] & 0x0FFFFFFF


def read_cluster_chain(
    reader: RawReader,
    bpb: FAT32BootSector,
    start_cluster: int,
    max_clusters: int = 0,
) -> tuple[list[int], str]:
    chain: list[int] = []
    cluster = start_cluster
    status = "ok"

    for _ in range(max_clusters if max_clusters > 0 else 10_000_000):
        if not is_valid_data_cluster(cluster):
            if is_end_of_chain(cluster):
                break
            if is_bad_cluster(cluster):
                status = "bad_cluster"
                break
            if is_free_cluster(cluster):
                if chain:
                    status = "truncated_free"
                else:
                    status = "free_start"
                break
            status = "invalid_cluster"
            break

        if cluster in chain:
            status = "loop_detected"
            break

        chain.append(cluster)
        cluster = get_next_cluster(reader, bpb, cluster)

        if cluster == 0:
            status = "zero_next"
            break

    return chain, status


def read_cluster_data(reader: RawReader, bpb: FAT32BootSector, cluster: int) -> bytes:
    if cluster < 2:
        return b""
    cluster_offset = bpb.data_start + (cluster - 2) * bpb.cluster_size
    return reader.read_at(cluster_offset, bpb.cluster_size)


def read_chain_data(reader: RawReader, bpb: FAT32BootSector, chain: list[int]) -> bytes:
    data = bytearray()
    for cluster in chain:
        data.extend(read_cluster_data(reader, bpb, cluster))
    return bytes(data)
