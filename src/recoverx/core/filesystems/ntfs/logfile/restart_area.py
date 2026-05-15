from __future__ import annotations

import struct

from .structures import LogFileHeader, RestartArea


def parse_restart_page(data: bytes, offset: int = 0) -> LogFileHeader | None:
    if len(data) - offset < 32:
        return None
    sig = data[offset : offset + 4]
    if sig not in (b"RSTR",):
        return None
    try:
        usa_offset = struct.unpack_from("<H", data, offset + 4)[0]
        usa_size = struct.unpack_from("<H", data, offset + 6)[0]
        last_lsn = struct.unpack_from("<Q", data, offset + 8)[0]
    except struct.error:
        return None
    major = struct.unpack_from("<H", data, offset + 16)[0]
    minor = struct.unpack_from("<H", data, offset + 18)[0]
    file_size = struct.unpack_from("<I", data, offset + 20)[0]
    page_size = struct.unpack_from("<I", data, offset + 24)[0]
    return LogFileHeader(
        signature=sig.decode("ascii", errors="replace"),
        usa_offset=usa_offset,
        usa_size=usa_size,
        last_lsn=last_lsn,
        major_version=major,
        minor_version=minor,
        file_size=file_size,
        page_size=page_size or 4096,
    )


def parse_restart_area(data: bytes, offset: int = 0) -> RestartArea | None:
    if len(data) - offset < 48:
        return None
    try:
        current_lsn = struct.unpack_from("<Q", data, offset + 0)[0]
        log_client_lsn = struct.unpack_from("<Q", data, offset + 8)[0]
        client_prev_lsn = struct.unpack_from("<Q", data, offset + 16)[0]
        client_next_lsn = struct.unpack_from("<Q", data, offset + 24)[0]
        area_length = struct.unpack_from("<I", data, offset + 40)[0]
        open_log_count = struct.unpack_from("<H", data, offset + 44)[0]
        last_lsn = struct.unpack_from("<Q", data, offset + 48)[0]
        oldest_lsn = struct.unpack_from("<Q", data, offset + 56)[0]
    except struct.error:
        return None
    return RestartArea(
        current_lsn=current_lsn,
        log_client_lsn=log_client_lsn,
        client_prev_lsn=client_prev_lsn,
        client_next_lsn=client_next_lsn,
        restart_area_length=area_length,
        open_log_count=open_log_count,
        last_lsn=last_lsn,
        oldest_lsn=oldest_lsn,
    )


def find_restart_pages(data: bytes, page_size: int = 4096) -> list[LogFileHeader]:
    pages: list[LogFileHeader] = []
    pos = 0
    max_pages = min(len(data) // page_size, 16)
    for _ in range(max_pages):
        if pos + 32 > len(data):
            break
        header = parse_restart_page(data, pos)
        if header:
            pages.append(header)
        pos += page_size
    return pages
