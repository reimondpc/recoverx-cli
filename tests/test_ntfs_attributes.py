from __future__ import annotations

import os
import random
import struct

from recoverx.core.filesystems.ntfs.attributes import (
    parse_attributes,
    parse_runlist,
)
from recoverx.core.filesystems.ntfs.structures import (
    ResidentAttribute,
    NonResidentAttribute,
)


def _make_resident_attr(attr_type: int = 0x10, value: bytes = b"test") -> bytes:
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


def _make_non_resident_attr(
    attr_type: int = 0x80, runs: list[tuple[int, int]] | None = None
) -> bytes:
    if runs is None:
        runs = [(10, 5)]
    runlist_data = bytearray()
    for count, offset in runs:
        count_bytes = _encode_variable(count)
        offset_bytes = _encode_signed_variable(offset)
        header = len(count_bytes) | (len(offset_bytes) << 4)
        runlist_data.append(header)
        runlist_data.extend(count_bytes)
        runlist_data.extend(offset_bytes)
    runlist_data.append(0)

    header_size = 64
    total_len = header_size + len(runlist_data)
    data = bytearray(total_len)
    struct.pack_into("<I", data, 0, attr_type)
    struct.pack_into("<I", data, 4, total_len)
    data[8] = 0x81
    data[9] = 0
    struct.pack_into("<H", data, 10, 0)
    struct.pack_into("<H", data, 12, 0)
    struct.pack_into("<H", data, 14, 0)
    struct.pack_into("<Q", data, 16, 0)
    struct.pack_into("<Q", data, 24, 0)
    struct.pack_into("<H", data, 32, header_size)
    data[34] = 0
    struct.pack_into("<Q", data, 40, 1000)
    struct.pack_into("<Q", data, 48, 500)
    struct.pack_into("<Q", data, 56, 500)
    data[header_size : header_size + len(runlist_data)] = runlist_data
    return bytes(data)


def _encode_variable(value: int) -> bytes:
    result = bytearray()
    while value > 0:
        result.append(value & 0xFF)
        value >>= 8
    return bytes(result) if result else b"\x00"


def _encode_signed_variable(value: int) -> bytes:
    abs_val = abs(value)
    result = bytearray()
    while abs_val > 0:
        result.append(abs_val & 0xFF)
        abs_val >>= 8
    if not result:
        result.append(0)
    if value < 0:
        result[-1] |= 0x80
    return bytes(result)


class TestParseAttributes:
    def test_parse_empty(self):
        assert parse_attributes(b"") == []

    def test_parse_terminator(self):
        data = b"\xff" * 16
        assert parse_attributes(data) == []

    def test_parse_single_resident(self):
        data = _make_resident_attr(0x10, b"\x00" * 72)
        attrs = parse_attributes(data)
        assert len(attrs) == 1
        assert attrs[0].attr_type == 0x10
        assert attrs[0].attr_type_name == "STANDARD_INFORMATION"
        assert attrs[0].non_resident is False

    def test_parse_single_non_resident(self):
        data = _make_non_resident_attr()
        attrs = parse_attributes(data)
        assert len(attrs) >= 1
        attr = attrs[0]
        assert attr.non_resident is True
        if isinstance(attr, NonResidentAttribute):
            assert attr.real_size == 500

    def test_parse_data_attribute(self):
        content = b"HELLO NTFS"
        data = _make_resident_attr(0x80, content)
        attrs = parse_attributes(data)
        assert len(attrs) == 1
        assert attrs[0].attr_type == 0x80
        if isinstance(attrs[0], ResidentAttribute):
            assert attrs[0].data == content

    def test_parse_file_name_attribute(self):
        name = b"TEST\x00FILE\x00"
        data = _make_resident_attr(0x30, name.ljust(68, b"\x00"))
        attrs = parse_attributes(data)
        assert len(attrs) == 1
        assert attrs[0].attr_type == 0x30


class TestRunlistParsing:
    def test_parse_empty(self):
        assert parse_runlist(b"\x00", 0) == []

    def test_parse_single_run(self):
        data = b"\x11\x0a\x05"
        runs = parse_runlist(data, 0)
        assert len(runs) == 1
        assert runs[0]["cluster_count"] == 10
        assert runs[0]["cluster_offset"] == 5

    def test_parse_terminated(self):
        data = b"\x11\x0a\x05\x00"
        runs = parse_runlist(data, 0)
        assert len(runs) == 1

    def test_parse_random(self):
        for _ in range(20):
            data = os.urandom(random.randint(1, 64))
            runs = parse_runlist(data, 0)
            assert isinstance(runs, list)

    def test_parse_large_offset(self):
        data = b"\x22\x14\x00\x14\x00"
        runs = parse_runlist(data, 0)
        assert len(runs) == 1
        assert runs[0]["cluster_count"] == 20

    def test_parse_negative_offset(self):
        data = b"\x11\x05\xfb"
        runs = parse_runlist(data, 0)
        assert len(runs) == 1
        assert runs[0]["cluster_offset"] < 0


class TestFuzzAttributes:
    def test_fuzz_random(self):
        for _ in range(30):
            data = os.urandom(random.randint(0, 4096))
            attrs = parse_attributes(data)
            assert isinstance(attrs, list)

    def test_fuzz_random_runlist(self):
        for _ in range(30):
            data = os.urandom(random.randint(0, 256))
            runs = parse_runlist(data, 0)
            assert isinstance(runs, list)
