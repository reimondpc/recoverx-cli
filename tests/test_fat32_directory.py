from __future__ import annotations

import struct

from recoverx.core.filesystems.fat32.directory import (
    parse_attributes,
    parse_date_only,
    parse_directory_entries,
    parse_timestamp,
)
from recoverx.core.filesystems.fat32.structures import FATAttributes, FATDirEntry


def _make_entry(
    name: bytes = b"FILE    ",
    ext: bytes = b"TXT",
    attr: int = 0x20,
    cluster_high: int = 0,
    cluster_low: int = 3,
    file_size: int = 1024,
    deleted: bool = False,
) -> bytes:
    entry = bytearray(32)
    if deleted:
        name = bytearray(name)
        name[0] = 0xE5
        name = bytes(name)
    entry[0:8] = name.ljust(8)[:8]
    entry[8:11] = ext.ljust(3)[:3]
    entry[11] = attr
    struct.pack_into("<H", entry, 20, cluster_high)
    struct.pack_into("<H", entry, 26, cluster_low)
    struct.pack_into("<I", entry, 28, file_size)
    return bytes(entry)


def _make_lfn_entries(name: str, seq: int = 0x41) -> list[bytes]:
    entries = []
    chars = name.encode("utf-16-le")
    chunk = chars[:10].ljust(10, b"\xff")
    entry = bytearray(32)
    entry[0] = seq
    entry[1:11] = chunk
    entry[11] = 0x0F
    chunk2 = chars[10:22].ljust(12, b"\xff")
    entry[14:26] = chunk2
    chunk3 = chars[22:26].ljust(4, b"\xff")
    entry[28:32] = chunk3
    entries.append(bytes(entry))
    return entries


class TestParseAttributes:
    def test_archive(self):
        attr = parse_attributes(0x20)
        assert attr.archive
        assert not attr.read_only

    def test_directory(self):
        attr = parse_attributes(0x10)
        assert attr.subdirectory
        assert not attr.archive

    def test_hidden(self):
        attr = parse_attributes(0x02)
        assert attr.hidden
        assert not attr.read_only

    def test_multiple(self):
        attr = parse_attributes(0x27)
        assert attr.archive
        assert attr.hidden
        assert attr.system
        assert attr.read_only

    def test_to_dict(self):
        attr = FATAttributes(read_only=True, hidden=True, archive=True)
        d = attr.to_dict()
        assert d["read_only"] is True
        assert d["hidden"] is True
        assert d["archive"] is True

    def test_str_representation(self):
        attr = FATAttributes(read_only=True, archive=True)
        assert "R" in str(attr)
        assert "A" in str(attr)

    def test_byte_property(self):
        attr = FATAttributes(read_only=True, archive=True)
        assert attr.byte & 0x01
        assert attr.byte & 0x20


class TestParseTimestamps:
    def test_parse_date_time(self):
        ts = parse_timestamp(0x4A3F, 0xA1B2)
        assert ts.year > 1980
        assert ts.month >= 1
        assert ts.day >= 1

    def test_parse_date_only(self):
        ts = parse_date_only(0x4A3F)
        assert ts.year > 1980
        assert ts.month >= 1

    def test_to_datetime(self):
        ts = parse_timestamp(0x4A3F, 0xA1B2)
        dt = ts.to_datetime()
        if dt:
            assert dt.year >= 1980

    def test_to_datetime_none(self):
        ts = parse_timestamp(0, 0)
        assert ts.to_datetime() is None

    def test_to_dict(self):
        ts = parse_timestamp(0x4A3F, 0xA1B2)
        d = ts.to_dict()
        assert "iso" in d
        assert "year" in d


class TestParseDirectoryEntries:
    def test_parse_single_file(self):
        entry = _make_entry()
        entries = parse_directory_entries(entry)
        assert len(entries) == 1
        assert entries[0].short_name == "FILE.TXT"
        assert entries[0].file_size == 1024
        assert entries[0].start_cluster == 3

    def test_parse_deleted_file(self):
        entry = _make_entry(deleted=True)
        entries = parse_directory_entries(entry)
        assert len(entries) == 1
        assert entries[0].deleted

    def test_parse_multiple_files(self):
        data = _make_entry(name=b"FIRST   ", ext=b"BIN", cluster_low=3)
        data += _make_entry(name=b"SECOND  ", ext=b"BIN", cluster_low=5)
        entries = parse_directory_entries(data)
        assert len(entries) == 2

    def test_parse_empty_data(self):
        assert parse_directory_entries(b"") == []

    def test_parse_free_marker_stops(self):
        data = _make_entry()
        data += b"\x00" * 32
        data += _make_entry(name=b"AFTER   ", ext=b"BIN")
        entries = parse_directory_entries(data)
        assert len(entries) == 1

    def test_parse_directory_attribute(self):
        entry = _make_entry(attr=0x10)
        entries = parse_directory_entries(entry)
        assert entries[0].is_directory

    def test_parse_lfn(self):
        lfns = _make_lfn_entries("LONGFILE.NAME.TXT")
        entry = _make_entry(name=b"LONGF~1 ", ext=b"TXT")
        data = b"".join(lfns) + entry
        entries = parse_directory_entries(data)
        assert len(entries) == 1
        assert "LONGFILE" in entries[0].long_name

    def test_file_to_dict(self):
        entry = _make_entry(name=b"TEST    ", ext=b"BIN", file_size=2048)
        parsed = parse_directory_entries(entry)[0]
        d = parsed.to_dict()
        assert d["short_name"] == "TEST.BIN"
        assert d["file_size"] == 2048
        assert d["attributes"] is not None


class TestFATDirEntry:
    def test_full_name_long(self):
        e = FATDirEntry(short_name="FILE.TXT", long_name="Long File Name.txt")
        assert e.full_name() == "Long File Name.txt"

    def test_full_name_short(self):
        e = FATDirEntry(short_name="FILE.TXT")
        assert e.full_name() == "FILE.TXT"
