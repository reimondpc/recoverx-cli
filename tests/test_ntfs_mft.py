from __future__ import annotations

import os
import struct

from recoverx.core.filesystems.ntfs.mft import (
    parse_mft_record,
    parse_mft_record_header,
    apply_fixups,
    read_mft_record,
)
from recoverx.core.filesystems.ntfs.structures import NTFSBootSector


def _make_file_record(
    flags: int = 1,
    mft_number: int = 0,
    attrs_data: bytes | None = None,
) -> bytes:
    record = bytearray(1024)
    record[0:4] = b"FILE"
    struct.pack_into("<H", record, 4, 48)
    struct.pack_into("<H", record, 6, 1)
    struct.pack_into("<H", record, 16, 1)
    struct.pack_into("<H", record, 18, 1)
    struct.pack_into("<H", record, 22, flags)
    struct.pack_into("<I", record, 24, 1024)
    struct.pack_into("<I", record, 28, 1024)
    struct.pack_into("<I", record, 44, mft_number)

    if attrs_data:
        attrs_offset = 48
        struct.pack_into("<H", record, 20, attrs_offset)
        record[attrs_offset : attrs_offset + len(attrs_data)] = attrs_data
        struct.pack_into("<I", record, 24, attrs_offset + len(attrs_data))
    else:
        terminator = b"\xff\xff\xff\xff" + b"\x00" * 12
        struct.pack_into("<H", record, 20, 48)
        record[48:64] = terminator
        struct.pack_into("<I", record, 24, 64)

    record[510] = 0x55
    record[511] = 0xAA
    return bytes(record)


def _make_resident_attr(attr_type: int, value: bytes) -> bytes:
    header_size = 24
    total_len = header_size + len(value)
    data = bytearray(total_len)
    struct.pack_into("<I", data, 0, attr_type)
    struct.pack_into("<I", data, 4, total_len)
    data[8] = 0x00
    data[9] = 0
    struct.pack_into("<H", data, 10, 0)
    struct.pack_into("<H", data, 12, 0)
    struct.pack_into("<H", data, 14, 0)
    struct.pack_into("<I", data, 16, len(value))
    struct.pack_into("<H", data, 20, header_size)
    data[header_size : header_size + len(value)] = value
    return bytes(data)


class _FakeReader:
    def __init__(self, data: bytes, size: int | None = None):
        self._data = data
        self._size = size or len(data)

    @property
    def size(self) -> int:
        return self._size

    def read_at(self, offset: int, size: int) -> bytes:
        if offset >= self._size:
            return b""
        return self._data[offset : offset + size]


class TestMFTRecordHeader:
    def test_parse_valid_header(self):
        data = _make_file_record()
        header = parse_mft_record_header(data)
        assert header is not None
        assert header.signature == "FILE"
        assert header.flags == 1
        assert header.in_use is True
        assert header.is_deleted is False

    def test_parse_empty(self):
        assert parse_mft_record_header(b"") is None

    def test_parse_wrong_signature(self):
        data = bytearray(48)
        data[0:4] = b"XXXX"
        assert parse_mft_record_header(bytes(data)) is None

    def test_parse_deleted_record(self):
        data = _make_file_record(flags=0)
        header = parse_mft_record_header(data)
        assert header is not None
        assert header.in_use is False
        assert header.is_deleted is True

    def test_parse_directory_record(self):
        data = _make_file_record(flags=3)
        header = parse_mft_record_header(data)
        assert header is not None
        assert header.in_use is True
        assert header.is_directory is True


class TestMFTRecord:
    def test_parse_valid_record(self):
        data = _make_file_record()
        record = parse_mft_record(data)
        assert record is not None
        assert record.header.signature == "FILE"
        assert record.header.mft_record_number == 0

    def test_parse_empty(self):
        assert parse_mft_record(b"") is None

    def test_parse_random_data(self):
        for _ in range(10):
            data = os.urandom(1024)
            record = parse_mft_record(data)
            assert record is None or isinstance(record.header.flags, int)

    def test_parse_with_attributes(self):
        si_data = struct.pack("<Q", 0) * 9
        si_attr = _make_resident_attr(0x10, si_data)
        fn_data = struct.pack("<Q", 0) * 8 + b"\x04\x00" + "TEST.TXT".encode("utf-16-le")
        fn_attr = _make_resident_attr(0x30, fn_data.ljust(68, b"\x00"))
        attrs = si_attr + fn_attr
        data = _make_file_record(attrs_data=attrs)
        record = parse_mft_record(data, 1024)
        assert record is not None
        assert len(record.attributes) >= 1

    def test_parse_with_data_attr(self):
        content = b"Hello NTFS Resident Data!"
        content_attr = _make_resident_attr(0x80, content)
        data = _make_file_record(attrs_data=content_attr)
        record = parse_mft_record(data, 1024)
        assert record is not None
        assert record.data_resident == content

    def test_fixups_applied(self):
        data = _make_file_record()
        data_arr = bytearray(data)
        fixup_offset = 48
        struct.pack_into("<H", data_arr, 4, fixup_offset)
        struct.pack_into("<H", data_arr, 6, 2)
        data_arr[fixup_offset] = 0xAA
        data_arr[fixup_offset + 1] = 0xBB
        data_arr[510] = 0xCC
        data_arr[511] = 0xDD
        data_arr[1022] = 0xEE
        data_arr[1023] = 0xFF
        header = parse_mft_record_header(bytes(data_arr))
        assert header is not None
        applied = apply_fixups(bytes(data_arr), header)
        assert isinstance(applied, bytes)

    def test_read_mft_record(self):
        data = _make_file_record()
        bpb = NTFSBootSector(
            bytes_per_sector=512,
            sectors_per_cluster=1,
            mft_cluster=16,
            clusters_per_file_record=1,
            total_sectors=1024,
        )
        image = bytearray(bpb.mft_byte_offset + 1024)
        image[bpb.mft_byte_offset : bpb.mft_byte_offset + 1024] = data
        reader = _FakeReader(bytes(image), len(image))
        record = read_mft_record(reader, bpb.mft_byte_offset, 1024)
        assert record is not None
        assert record.header.signature == "FILE"


class TestRecovery:
    def test_recover_resident_data(self):
        content = b"RESIDENT DATA FOR RECOVERY"
        content_attr = _make_resident_attr(0x80, content)
        data = _make_file_record(attrs_data=content_attr)
        record = parse_mft_record(data, 1024)
        assert record is not None
        assert record.data_resident == content

    def test_mft_record_to_dict(self):
        data = _make_file_record(mft_number=42)
        record = parse_mft_record(data)
        assert record is not None
        d = record.to_dict()
        assert d["header"]["mft_record_number"] == 42
        assert "is_deleted" in d
        assert "is_directory" in d
