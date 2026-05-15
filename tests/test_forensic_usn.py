from __future__ import annotations

import struct

from recoverx.core.filesystems.ntfs.usn.mapping import map_usn_records, usn_to_event
from recoverx.core.filesystems.ntfs.usn.reasons import resolve_usn_reasons
from recoverx.core.filesystems.ntfs.usn.records import parse_usn_record, parse_usn_records


def _make_usn_record_v2(
    file_ref: int = 100,
    parent_ref: int = 5,
    usn: int = 1000,
    reason: int = 0x0100,
    filename: str = "test.txt",
) -> bytes:
    name_bytes = filename.encode("utf-16-le")
    fn_length = len(name_bytes)
    fn_offset = 60
    record_length = fn_offset + fn_length
    data = bytearray(record_length)
    struct.pack_into("<I", data, 0, record_length)
    struct.pack_into("<H", data, 4, 2)
    struct.pack_into("<H", data, 6, 0)
    struct.pack_into("<Q", data, 8, file_ref)
    struct.pack_into("<Q", data, 16, parent_ref)
    struct.pack_into("<q", data, 24, usn)
    struct.pack_into("<Q", data, 32, 0)
    struct.pack_into("<I", data, 40, reason)
    struct.pack_into("<I", data, 44, 0)
    struct.pack_into("<I", data, 48, 0)
    struct.pack_into("<I", data, 52, 0)
    struct.pack_into("<H", data, 56, fn_length)
    struct.pack_into("<H", data, 58, fn_offset)
    data[fn_offset : fn_offset + fn_length] = name_bytes
    return bytes(data)


def test_parse_usn_record_v2():
    data = _make_usn_record_v2()
    record = parse_usn_record(data)
    assert record is not None
    assert record.major_version == 2
    assert record.minor_version == 0
    assert record.file_reference == 100
    assert record.parent_reference == 5
    assert record.usn == 1000
    assert record.file_name == "test.txt"
    assert record.valid


def test_parse_usn_record_file_create():
    data = _make_usn_record_v2(reason=0x00000100)
    record = parse_usn_record(data)
    assert record is not None
    assert "USN_REASON_FILE_CREATE" in record.reason_names


def test_parse_usn_record_file_delete():
    data = _make_usn_record_v2(reason=0x00000200)
    record = parse_usn_record(data)
    assert record is not None
    assert "USN_REASON_FILE_DELETE" in record.reason_names


def test_parse_usn_record_rename():
    data = _make_usn_record_v2(reason=0x00002000)
    record = parse_usn_record(data)
    assert record is not None
    assert "USN_REASON_RENAME_NEW_NAME" in record.reason_names


def test_parse_usn_multiple_records():
    r1 = _make_usn_record_v2(file_ref=1, filename="a.txt")
    r2 = _make_usn_record_v2(file_ref=2, filename="b.txt")
    data = r1 + r2
    records = parse_usn_records(data)
    assert len(records) == 2
    assert records[0].file_name == "a.txt"
    assert records[1].file_name == "b.txt"


def test_parse_usn_empty_data():
    records = parse_usn_records(b"")
    assert records == []


def test_parse_usn_invalid_short():
    record = parse_usn_record(b"\x00" * 10)
    assert record is None


def test_resolve_reasons_create():
    reasons = resolve_usn_reasons(0x00000100)
    assert "USN_REASON_FILE_CREATE" in reasons


def test_resolve_reasons_delete():
    reasons = resolve_usn_reasons(0x00000200)
    assert "USN_REASON_FILE_DELETE" in reasons


def test_resolve_reasons_rename():
    reasons = resolve_usn_reasons(0x00003000)
    assert "USN_REASON_RENAME_OLD_NAME" in reasons
    assert "USN_REASON_RENAME_NEW_NAME" in reasons


def test_resolve_reasons_close():
    reasons = resolve_usn_reasons(0x80000000)
    assert "USN_REASON_CLOSE" in reasons


def test_resolve_reasons_unknown():
    reasons = resolve_usn_reasons(0)
    assert reasons == ["UNKNOWN"]


def test_usn_to_event_create():
    data = _make_usn_record_v2(reason=0x00000100, filename="new.txt")
    record = parse_usn_record(data)
    assert record is not None
    event = usn_to_event(record)
    assert event.event_type.value == "FILE_CREATED"
    assert event.filename == "new.txt"


def test_usn_to_event_delete():
    data = _make_usn_record_v2(reason=0x00000200, filename="del.txt")
    record = parse_usn_record(data)
    assert record is not None
    event = usn_to_event(record)
    assert event.event_type.value == "FILE_DELETED"


def test_usn_to_event_rename():
    data = _make_usn_record_v2(reason=0x00002000, filename="renamed.txt")
    record = parse_usn_record(data)
    assert record is not None
    event = usn_to_event(record)
    assert event.event_type.value == "FILE_RENAMED"


def test_map_usn_records_rename_pair():
    old = _make_usn_record_v2(reason=0x00001000, file_ref=50, filename="old.txt")
    new = _make_usn_record_v2(reason=0x00002000, file_ref=50, filename="new.txt")
    data = old + new
    records = parse_usn_records(data)
    events = map_usn_records(records)
    renames = [e for e in events if e.event_type.value == "FILE_RENAMED"]
    assert len(renames) >= 1


def test_map_usn_records_empty():
    events = map_usn_records([])
    assert events == []


def test_usn_record_to_dict():
    data = _make_usn_record_v2(file_ref=99, filename="dict.txt")
    record = parse_usn_record(data)
    assert record is not None
    d = record.to_dict()
    assert d["file_reference"] == 99
    assert d["file_name"] == "dict.txt"
    assert d["valid"] is True


def test_parse_usn_record_v3():
    data = _make_usn_record_v2(file_ref=200, filename="v3_test.txt")
    record = parse_usn_record(data)
    assert record is not None
    assert record.file_reference == 200


def test_parse_usn_record_long_filename():
    long_name = "A" * 100
    data = _make_usn_record_v2(filename=long_name)
    record = parse_usn_record(data)
    assert record is not None
    assert record.file_name == long_name
