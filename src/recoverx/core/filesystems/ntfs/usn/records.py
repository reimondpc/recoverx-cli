from __future__ import annotations

import struct
from datetime import datetime, timezone

from .reasons import resolve_usn_reasons
from .structures import USNRecord

EPOCH_FILETIME = 116444736000000000


def _filetime_to_datetime(filetime: int) -> datetime | None:
    if filetime == 0:
        return None
    try:
        ticks = filetime - EPOCH_FILETIME
        seconds = ticks / 10000000
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    except (OSError, OverflowError, ValueError):
        return None


def _parse_utf16le_name(data: bytes, offset: int, length_bytes: int) -> str:
    try:
        return data[offset:offset + length_bytes].decode("utf-16-le", errors="replace")
    except (UnicodeDecodeError, ValueError):
        return ""


def parse_usn_record(data: bytes, offset: int = 0) -> USNRecord | None:
    remaining = len(data) - offset
    if remaining < 24:
        return None

    try:
        record_length = struct.unpack_from("<I", data, offset)[0]
    except struct.error:
        return None

    if record_length < 24 or record_length > remaining:
        return None

    try:
        major_version = struct.unpack_from("<H", data, offset + 4)[0]
        minor_version = struct.unpack_from("<H", data, offset + 6)[0]
    except struct.error:
        return None

    if major_version not in (2, 3):
        return None

    try:
        file_ref = struct.unpack_from("<Q", data, offset + 8)[0]
        parent_ref = struct.unpack_from("<Q", data, offset + 16)[0]
        usn = struct.unpack_from("<q", data, offset + 24)[0]
        timestamp_raw = struct.unpack_from("<Q", data, offset + 32)[0]
        reason_flags = struct.unpack_from("<I", data, offset + 40)[0]
        source_info = struct.unpack_from("<I", data, offset + 44)[0]
        security_id = struct.unpack_from("<I", data, offset + 48)[0]
        file_attributes = struct.unpack_from("<I", data, offset + 52)[0]
        fn_length = struct.unpack_from("<H", data, offset + 56)[0]
        fn_offset = struct.unpack_from("<H", data, offset + 58)[0]
    except struct.error:
        return None

    if fn_offset + fn_length > record_length:
        return None

    file_name = _parse_utf16le_name(data, offset + fn_offset, fn_length)
    timestamp = _filetime_to_datetime(timestamp_raw)
    reason_names = resolve_usn_reasons(reason_flags)

    return USNRecord(
        record_length=record_length,
        major_version=major_version,
        minor_version=minor_version,
        file_reference=file_ref,
        parent_reference=parent_ref,
        usn=usn,
        timestamp=timestamp,
        reason_flags=reason_flags,
        reason_names=reason_names,
        source_info=source_info,
        security_id=security_id,
        file_attributes=file_attributes,
        file_name=file_name,
        raw_offset=offset,
        raw_data=data[offset:offset + record_length],
    )


def parse_usn_records(data: bytes, offset: int = 0) -> list[USNRecord]:
    records: list[USNRecord] = []
    pos = offset
    max_iterations = len(data) // 24
    iterations = 0

    while pos + 24 <= len(data) and iterations < max_iterations:
        iterations += 1
        record = parse_usn_record(data, pos)
        if record is None:
            pos += 4
            continue
        records.append(record)
        if record.record_length < 24:
            break
        pos += record.record_length

    return records
