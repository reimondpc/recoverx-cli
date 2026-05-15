from __future__ import annotations

import logging
import struct

from recoverx.core.utils.raw_reader import RawReader

from .fat_table import read_cluster_chain, read_cluster_data
from .structures import FAT32BootSector, FATAttributes, FATDirEntry, FATTimestamp

logger = logging.getLogger("recoverx")

DELETED_MARKER = 0xE5
FREE_MARKER = 0x00
DOT_MARKER = 0x2E
LFN_ATTR = 0x0F


def parse_timestamp(date_word: int, time_word: int) -> FATTimestamp:
    return FATTimestamp(
        year=((date_word >> 9) & 0x7F) + 1980,
        month=(date_word >> 5) & 0x0F,
        day=date_word & 0x1F,
        hour=(time_word >> 11) & 0x1F,
        minute=(time_word >> 5) & 0x3F,
        second=(time_word & 0x1F) * 2,
    )


def parse_date_only(date_word: int) -> FATTimestamp:
    return FATTimestamp(
        year=((date_word >> 9) & 0x7F) + 1980,
        month=(date_word >> 5) & 0x0F,
        day=date_word & 0x1F,
    )


def parse_attributes(attr_byte: int) -> FATAttributes:
    return FATAttributes(
        read_only=bool(attr_byte & 0x01),
        hidden=bool(attr_byte & 0x02),
        system=bool(attr_byte & 0x04),
        volume_label=bool(attr_byte & 0x08),
        subdirectory=bool(attr_byte & 0x10),
        archive=bool(attr_byte & 0x20),
        device=bool(attr_byte & 0x40),
    )


def parse_short_name(raw_name: bytes, raw_ext: bytes) -> tuple[str, str]:
    name = raw_name.decode("ascii", errors="replace").rstrip().rstrip("\xff")
    ext = raw_ext.decode("ascii", errors="replace").rstrip().rstrip("\xff")
    return name, ext


def parse_lfn_entries(entries: list[bytes]) -> str:
    chars: list[str] = []

    for entry in reversed(entries):
        if len(entry) < 32:
            continue
        name1 = entry[1:11]
        name2 = entry[14:26]
        name3 = entry[28:32]
        raw = name1 + name2 + name3
        for i in range(0, len(raw), 2):
            if i + 1 < len(raw):
                code = raw[i] | (raw[i + 1] << 8)
                if code == 0xFFFF or code == 0x0000:
                    break
                if 0x20 <= code <= 0xFFFD:
                    chars.append(chr(code))

    return "".join(chars).rstrip("\x00").rstrip("\xff").strip()


def parse_directory_entries(data: bytes, base_offset: int = 0) -> list[FATDirEntry]:
    entries: list[FATDirEntry] = []
    lfn_buffer: list[bytes] = []

    i = 0
    while i + 32 <= len(data):
        entry = data[i : i + 32]
        offset = base_offset + i
        first_byte = entry[0]

        if first_byte == FREE_MARKER:
            break

        attr = entry[11]

        if attr == LFN_ATTR:
            lfn_buffer.append(entry)
            i += 32
            continue

        is_deleted = first_byte == DELETED_MARKER

        raw_name = bytearray(entry[0:8])
        if is_deleted:
            raw_name[0] = 0x3F

        raw_name_bytes = bytes(raw_name)
        raw_ext = entry[8:11]

        name, ext = parse_short_name(raw_name_bytes, raw_ext)
        short_name = (name + "." + ext).rstrip(".") if ext else name

        dir_attr = parse_attributes(attr)

        if dir_attr.volume_label:
            label = raw_name_bytes.decode("ascii", errors="replace").rstrip()
            entries.append(
                FATDirEntry(
                    name=label,
                    short_name=label,
                    attributes=dir_attr,
                    is_volume_label=True,
                    offset_in_image=offset,
                    original_raw=entry,
                )
            )
            i += 32
            lfn_buffer.clear()
            continue

        is_dir = dir_attr.subdirectory
        is_dot = raw_name_bytes[0:1] == b"."

        first_cluster_high = struct.unpack_from("<H", entry, 20)[0]
        first_cluster_low = struct.unpack_from("<H", entry, 26)[0]
        start_cluster = (first_cluster_high << 16) | first_cluster_low

        file_size = struct.unpack_from("<I", entry, 28)[0]

        c_time = struct.unpack_from("<H", entry, 14)[0]
        c_date = struct.unpack_from("<H", entry, 16)[0]
        a_date = struct.unpack_from("<H", entry, 18)[0]
        m_time = struct.unpack_from("<H", entry, 22)[0]
        m_date = struct.unpack_from("<H", entry, 24)[0]

        long_name = parse_lfn_entries(lfn_buffer)

        dir_entry = FATDirEntry(
            name=short_name,
            extension=ext,
            short_name=short_name,
            long_name=long_name or "",
            attributes=dir_attr,
            deleted=is_deleted,
            is_directory=is_dir or is_dot,
            is_volume_label=False,
            start_cluster=start_cluster,
            file_size=file_size,
            created=parse_timestamp(c_date, c_time),
            last_accessed=parse_date_only(a_date),
            last_modified=parse_timestamp(m_date, m_time),
            offset_in_image=offset,
            original_raw=entry,
        )
        entries.append(dir_entry)
        i += 32
        lfn_buffer.clear()

    return entries


def read_directory(
    reader: RawReader,
    bpb: FAT32BootSector,
    cluster: int,
    max_size: int = 0,
) -> list[FATDirEntry]:
    chain, status = read_cluster_chain(reader, bpb, cluster)
    if not chain:
        logger.warning("Cannot read directory at cluster %d: %s", cluster, status)
        return []

    data = bytearray()
    for c in chain:
        data.extend(read_cluster_data(reader, bpb, c))
        if max_size and len(data) >= max_size:
            break

    return parse_directory_entries(bytes(data))


def walk_directory_tree(
    reader: RawReader,
    bpb: FAT32BootSector,
    cluster: int = 0,
    path: str = "",
    max_depth: int = 32,
) -> list[tuple[str, FATDirEntry]]:
    results: list[tuple[str, FATDirEntry]] = []
    root = cluster if cluster != 0 else bpb.root_cluster
    _walk(reader, bpb, root, path, results, 0, max_depth)
    return results


def _walk(
    reader: RawReader,
    bpb: FAT32BootSector,
    cluster: int,
    path: str,
    results: list[tuple[str, FATDirEntry]],
    depth: int,
    max_depth: int,
) -> None:
    if depth > max_depth:
        return

    entries = read_directory(reader, bpb, cluster)
    visited_clusters: set[int] = set()

    for entry in entries:
        if entry.is_volume_label:
            continue
        if entry.deleted:
            continue

        full_path = f"{path}/{entry.short_name}" if path else entry.short_name

        if entry.is_directory and entry.short_name not in (".", ".."):
            results.append((full_path, entry))
            if entry.start_cluster >= 2 and entry.start_cluster not in visited_clusters:
                visited_clusters.add(entry.start_cluster)
                _walk(reader, bpb, entry.start_cluster, full_path, results, depth + 1, max_depth)
        elif not entry.is_directory:
            results.append((full_path, entry))
