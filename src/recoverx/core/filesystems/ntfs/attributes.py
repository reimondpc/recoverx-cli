from __future__ import annotations

import logging
import struct

from .constants import ATTR_NAMES
from .structures import (
    NTFSAttribute,
    ResidentAttribute,
    NonResidentAttribute,
)

logger = logging.getLogger("recoverx")


def parse_attribute_header(data: bytes, offset: int) -> NTFSAttribute | None:
    if len(data) < offset + 4:
        return None

    attr_type = struct.unpack_from("<I", data, offset)[0]
    if attr_type == 0xFFFFFFFF:
        return None

    if len(data) < offset + 16:
        return None

    try:
        length = struct.unpack_from("<I", data, offset + 4)[0]
        non_resident = bool(data[offset + 8] & 0x80)
        name_length = data[offset + 9]
        name_offset = struct.unpack_from("<H", data, offset + 10)[0]
        flags = struct.unpack_from("<H", data, offset + 12)[0]
        attr_id = struct.unpack_from("<H", data, offset + 14)[0]

        name = ""
        if name_length > 0 and name_offset > 0:
            name_bytes = data[name_offset : name_offset + name_length * 2]
            name = name_bytes.decode("utf-16-le", errors="replace")

        attr_type_name = ATTR_NAMES.get(attr_type, f"UNKNOWN_0x{attr_type:02X}")

        if non_resident:
            return _parse_non_resident(
                data, offset, length, attr_type, attr_type_name, name_length,
                name_offset, name, flags, attr_id,
            )
        else:
            return _parse_resident(
                data, offset, length, attr_type, attr_type_name, name_length,
                name_offset, name, flags, attr_id,
            )
    except (struct.error, IndexError):
        return None


def _parse_resident(
    data: bytes, offset: int, length: int,
    attr_type: int, attr_type_name: str, name_length: int,
    name_offset: int, name: str, flags: int, attr_id: int,
) -> ResidentAttribute | None:
    if len(data) < offset + 24:
        return None

    try:
        value_length = struct.unpack_from("<I", data, offset + 16)[0]
        value_offset_rel = struct.unpack_from("<H", data, offset + 20)[0]
        value_offset_abs = offset + value_offset_rel
        value_data = data[value_offset_abs : value_offset_abs + value_length]

        return ResidentAttribute(
            attr_type=attr_type,
            attr_type_name=attr_type_name,
            length=length,
            non_resident=False,
            name_length=name_length,
            name_offset=name_offset,
            name=name,
            flags=flags,
            attr_id=attr_id,
            value_length=value_length,
            value_offset=value_offset_rel,
            data=value_data,
        )
    except (struct.error, IndexError):
        return None


def _parse_non_resident(
    data: bytes, offset: int, length: int,
    attr_type: int, attr_type_name: str, name_length: int,
    name_offset: int, name: str, flags: int, attr_id: int,
) -> NonResidentAttribute | None:
    if len(data) < offset + 64:
        return None

    try:
        starting_vcn = struct.unpack_from("<Q", data, offset + 16)[0]
        last_vcn = struct.unpack_from("<Q", data, offset + 24)[0]
        runlist_offset = struct.unpack_from("<H", data, offset + 32)[0]
        compression_unit = data[offset + 34]
        allocated_size = struct.unpack_from("<Q", data, offset + 40)[0]
        real_size = struct.unpack_from("<Q", data, offset + 48)[0]
        initialised_size = struct.unpack_from("<Q", data, offset + 56)[0]

        abs_runlist_offset = offset + runlist_offset
        data_runs = parse_runlist(data, abs_runlist_offset)

        return NonResidentAttribute(
            attr_type=attr_type,
            attr_type_name=attr_type_name,
            length=length,
            non_resident=True,
            name_length=name_length,
            name_offset=name_offset,
            name=name,
            flags=flags,
            attr_id=attr_id,
            starting_vcn=starting_vcn,
            last_vcn=last_vcn,
            runlist_offset=runlist_offset,
            compression_unit=compression_unit,
            allocated_size=allocated_size,
            real_size=real_size,
            initialised_size=initialised_size,
            data_runs=data_runs,
        )
    except (struct.error, IndexError):
        return None


def parse_runlist(data: bytes, offset: int) -> list[dict]:
    runs: list[dict] = []
    pos = offset

    while pos < len(data):
        header_byte = data[pos]
        if header_byte == 0:
            break

        count_bytes = header_byte & 0x0F
        offset_bytes = (header_byte >> 4) & 0x0F

        if pos + 1 + count_bytes + offset_bytes > len(data):
            break

        cluster_count = 0
        for i in range(count_bytes):
            cluster_count |= data[pos + 1 + i] << (8 * i)

        cluster_offset = 0
        if offset_bytes > 0:
            raw_offset = 0
            for i in range(offset_bytes):
                raw_offset |= data[pos + 1 + count_bytes + i] << (8 * i)
            if raw_offset & (1 << (offset_bytes * 8 - 1)):
                raw_offset |= -1 - (1 << (offset_bytes * 8)) + 1
            cluster_offset = raw_offset

        runs.append({
            "cluster_count": cluster_count,
            "cluster_offset": cluster_offset,
        })
        pos += 1 + count_bytes + offset_bytes

    return runs


def parse_attributes(data: bytes) -> list[NTFSAttribute]:
    attributes: list[NTFSAttribute] = []
    offset = 0

    while offset < len(data):
        attr = parse_attribute_header(data, offset)
        if attr is None:
            break

        attributes.append(attr)

        if attr.length == 0:
            break

        offset += attr.length

    return attributes
