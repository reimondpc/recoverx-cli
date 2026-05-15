from __future__ import annotations

import struct

from recoverx.core.filesystems.ntfs.logfile.records import parse_log_record, parse_log_records
from recoverx.core.filesystems.ntfs.logfile.restart_area import (
    find_restart_pages,
    parse_restart_page,
)
from recoverx.core.filesystems.ntfs.logfile.structures import LogFileHeader


def _make_restart_page() -> bytes:
    data = bytearray(4096)
    data[0:4] = b"RSTR"
    struct.pack_into("<H", data, 4, 48)
    struct.pack_into("<H", data, 6, 3)
    struct.pack_into("<Q", data, 8, 100)
    struct.pack_into("<H", data, 16, 1)
    struct.pack_into("<H", data, 18, 0)
    struct.pack_into("<I", data, 20, 4096 * 64)
    struct.pack_into("<I", data, 24, 4096)
    return bytes(data)


def _make_log_record(
    lsn: int = 1,
    prev_lsn: int = 0,
    rec_type: int = 0x05,
    mft_ref: int = 45,
) -> bytes:
    data = bytearray(64)
    data[0:4] = b"RCRD"
    struct.pack_into("<Q", data, 8, lsn)
    struct.pack_into("<Q", data, 16, prev_lsn)
    struct.pack_into("<I", data, 28, 1)
    struct.pack_into("<H", data, 32, rec_type)
    struct.pack_into("<I", data, 36, 100)
    struct.pack_into("<H", data, 40, 0)
    struct.pack_into("<H", data, 42, 64)
    struct.pack_into("<H", data, 48, 8)
    struct.pack_into("<H", data, 50, 7)
    struct.pack_into("<Q", data, 56, mft_ref)
    return bytes(data)


def test_parse_restart_page():
    data = _make_restart_page()
    header = parse_restart_page(data)
    assert header is not None
    assert header.signature == "RSTR"
    assert header.last_lsn == 100
    assert header.page_size == 4096
    assert header.valid


def test_parse_restart_page_invalid():
    header = parse_restart_page(b"\x00" * 32)
    assert header is None


def test_parse_restart_page_short():
    header = parse_restart_page(b"\x00" * 10)
    assert header is None


def test_find_restart_pages():
    page = _make_restart_page()
    data = page + b"\x00" * 4096 + page
    pages = find_restart_pages(data, 4096)
    assert len(pages) == 2


def test_parse_log_record():
    raw = _make_log_record(lsn=42, rec_type=0x05, mft_ref=100)
    record = parse_log_record(raw)
    assert record is not None
    assert record.lsn == 42
    assert record.record_type_name in (
        "UpdateResidentValue",
        "CreateAttribute",
        "UpdateNonresidentValue",
    )


def test_parse_log_record_short():
    record = parse_log_record(b"\x00" * 10)
    assert record is None


def test_parse_log_records_multiple():
    r1 = _make_log_record(lsn=1)
    r2 = _make_log_record(lsn=2)
    r3 = _make_log_record(lsn=3)
    data = r1 + r2 + r3
    records = parse_log_records(data)
    assert len(records) == 3
    assert records[0].lsn == 1
    assert records[1].lsn == 2
    assert records[2].lsn == 3


def test_parse_log_records_empty():
    records = parse_log_records(b"")
    assert records == []


def test_parse_log_records_max():
    r1 = _make_log_record(lsn=1)
    r2 = _make_log_record(lsn=2)
    data = r1 + r2
    records = parse_log_records(data, max_records=1)
    assert len(records) == 1


def test_log_record_operation_names():
    raw = _make_log_record(rec_type=0x05)
    record = parse_log_record(raw)
    assert record is not None
    assert record.redo_operation in ("UpdateResidentValue", "UpdateNonresidentValue")


def test_log_record_target_mft():
    raw = _make_log_record(mft_ref=200)
    record = parse_log_record(raw)
    assert record is not None
    assert record.target_mft == 200


def test_log_record_to_dict():
    raw = _make_log_record(lsn=99)
    record = parse_log_record(raw)
    assert record is not None
    d = record.to_dict()
    assert d["lsn"] == 99
    assert d["valid"] is True


def test_log_file_header_to_dict():
    header = LogFileHeader(
        signature="RSTR",
        usa_offset=48,
        usa_size=3,
        last_lsn=200,
        page_size=4096,
    )
    d = header.to_dict()
    assert d["signature"] == "RSTR"
    assert d["last_lsn"] == 200


def test_log_record_unknown_type():
    raw = _make_log_record(rec_type=0xFF)
    record = parse_log_record(raw)
    assert record is not None
    assert "UNKNOWN" in record.record_type_name


def test_parse_log_record_invalid_flags():
    data = b"\x00" * 48
    record = parse_log_record(data)
    assert record is not None


def test_log_record_prev_lsn():
    raw = _make_log_record(lsn=5, prev_lsn=3)
    record = parse_log_record(raw)
    assert record is not None
    assert record.previous_lsn == 3
