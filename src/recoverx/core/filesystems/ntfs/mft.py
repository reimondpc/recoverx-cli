from __future__ import annotations

import logging
import struct
from datetime import datetime, timedelta, timezone

from recoverx.core.utils.raw_reader import RawReader

from .attributes import parse_attributes
from .constants import FILE_RECORD_SIGNATURE
from .structures import (
    MFTRecord,
    MFTRecordHeader,
)

logger = logging.getLogger("recoverx")


def parse_mft_record_header(data: bytes, offset: int = 0) -> MFTRecordHeader | None:
    if len(data) < offset + 48:
        return None

    sig = data[offset : offset + 4]
    if sig != FILE_RECORD_SIGNATURE:
        return None

    try:
        fixup_offset = struct.unpack_from("<H", data, offset + 4)[0]
        fixup_count = struct.unpack_from("<H", data, offset + 6)[0]
        lsn = struct.unpack_from("<Q", data, offset + 8)[0]
        seq = struct.unpack_from("<H", data, offset + 16)[0]
        link_count = struct.unpack_from("<H", data, offset + 18)[0]
        attrs_offset = struct.unpack_from("<H", data, offset + 20)[0]
        flags = struct.unpack_from("<H", data, offset + 22)[0]
        used_size = struct.unpack_from("<I", data, offset + 24)[0]
        allocated_size = struct.unpack_from("<I", data, offset + 28)[0]
        mft_record_number = struct.unpack_from("<I", data, offset + 44)[0]

        return MFTRecordHeader(
            signature=sig.decode("ascii", errors="replace"),
            fixup_offset=fixup_offset,
            fixup_count=fixup_count,
            log_sequence_number=lsn,
            sequence_number=seq,
            link_count=link_count,
            attrs_offset=attrs_offset,
            flags=flags,
            used_size=used_size,
            allocated_size=allocated_size,
            mft_record_number=mft_record_number,
        )
    except (struct.error, IndexError):
        return None


def apply_fixups(data: bytes, header: MFTRecordHeader) -> bytes:
    if header.fixup_offset <= 0 or header.fixup_count <= 0:
        return data

    record_size = len(data)
    sector_size = 512

    try:
        fixup_values = struct.unpack_from(f"<{header.fixup_count}H", data, header.fixup_offset)
        for i in range(1, header.fixup_count):
            sector_end = i * sector_size - 2
            if 0 <= sector_end < record_size - 1:
                data_arr = bytearray(data)
                struct.pack_into("<H", data_arr, sector_end, fixup_values[i])
                data = bytes(data_arr)

        return data
    except (struct.error, IndexError):
        return data


def parse_mft_record(data: bytes, record_size: int = 1024) -> MFTRecord | None:
    header = parse_mft_record_header(data)
    if header is None:
        return None

    applied = apply_fixups(data, header)
    attrs_data = applied[header.attrs_offset : header.used_size]
    attributes = parse_attributes(attrs_data)

    record = MFTRecord(
        header=header,
        attributes=attributes,
        raw_data=applied,
    )

    resident_data = b""
    for attr in attributes:
        from .structures import (
            FileNameAttribute,
            NonResidentAttribute,
            ResidentAttribute,
            StandardInformation,
        )

        if attr.attr_type == 0x10 and hasattr(attr, "data"):
            if len(attr.data) >= 72:
                try:
                    record.standard_info = StandardInformation(
                        created=_parse_ts(attr.data, 0),
                        modified=_parse_ts(attr.data, 8),
                        mft_modified=_parse_ts(attr.data, 16),
                        accessed=_parse_ts(attr.data, 24),
                        flags=struct.unpack_from("<I", attr.data, 32)[0],
                    )
                except (struct.error, IndexError):
                    pass

        elif attr.attr_type == 0x30 and hasattr(attr, "data"):
            if len(attr.data) >= 68:
                try:
                    parent_ref = struct.unpack_from("<Q", attr.data, 0)[0]
                    parent_mft = parent_ref & 0xFFFFFFFFFFFFFFFF
                    parent_seq = parent_ref >> 48
                    name_len = attr.data[64]
                    name_type = attr.data[65]
                    name_bytes = attr.data[66 : 66 + name_len * 2]
                    name = name_bytes.decode("utf-16-le", errors="replace")

                    record.file_name = FileNameAttribute(
                        parent_mft=parent_mft & 0xFFFFFFFF,
                        parent_seq=parent_seq,
                        created=_parse_ts(attr.data, 8),
                        modified=_parse_ts(attr.data, 16),
                        mft_modified=_parse_ts(attr.data, 24),
                        accessed=_parse_ts(attr.data, 32),
                        allocated_size=struct.unpack_from("<Q", attr.data, 40)[0],
                        real_size=struct.unpack_from("<Q", attr.data, 48)[0],
                        flags=struct.unpack_from("<I", attr.data, 56)[0],
                        name_length=name_len,
                        name_type=name_type,
                        name=name,
                    )
                except (struct.error, IndexError):
                    pass

        elif attr.attr_type == 0x80:
            if isinstance(attr, ResidentAttribute) and hasattr(attr, "data"):
                resident_data = attr.data
                record.resident = True
            elif isinstance(attr, NonResidentAttribute):
                record.data_non_resident = attr
                record.resident = False

    record.data_resident = resident_data
    return record


def _parse_ts(data: bytes, offset: int) -> datetime | None:
    ts = struct.unpack_from("<Q", data, offset)[0]
    if ts == 0:
        return None
    try:
        return datetime(1601, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=ts // 10)
    except (OverflowError, ValueError):
        return None


def read_mft_record(reader: RawReader, byte_offset: int, record_size: int) -> MFTRecord | None:
    if byte_offset + record_size > reader.size:
        return None
    data = reader.read_at(byte_offset, record_size)
    if len(data) < record_size:
        return None
    return parse_mft_record(data, record_size)
