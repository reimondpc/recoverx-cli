from __future__ import annotations

import os
import random
import struct

from recoverx.core.filesystems.ntfs.logfile.records import parse_log_record, parse_log_records
from recoverx.core.filesystems.ntfs.logfile.restart_area import (
    find_restart_pages,
    parse_restart_area,
    parse_restart_page,
)


class TestFuzzLogFile:
    def test_fuzz_restart_page(self):
        for _ in range(50):
            data = os.urandom(random.randint(32, 512))
            header = parse_restart_page(data)
            if header:
                assert isinstance(header.signature, str)

    def test_fuzz_log_record(self):
        for _ in range(50):
            data = os.urandom(random.randint(24, 256))
            record = parse_log_record(data)
            if record:
                assert isinstance(record.lsn, int)

    def test_fuzz_log_records_empty(self):
        for _ in range(20):
            records = parse_log_records(os.urandom(random.randint(0, 64)))
            assert isinstance(records, list)

    def test_fuzz_log_records_corrupted(self):
        for _ in range(30):
            data = bytearray(random.randint(48, 512))
            for i in range(len(data)):
                data[i] = random.randint(0, 255)
            records = parse_log_records(bytes(data))
            assert isinstance(records, list)

    def test_fuzz_restart_area(self):
        for _ in range(30):
            data = os.urandom(random.randint(48, 128))
            area = parse_restart_area(data)
            if area:
                assert isinstance(area.last_lsn, int)

    def test_fuzz_find_restart_pages(self):
        for _ in range(20):
            data = os.urandom(random.randint(0, 8192))
            pages = find_restart_pages(data, 4096)
            assert isinstance(pages, list)

    def test_fuzz_log_record_extreme_lsn(self):
        for _ in range(20):
            data = bytearray(64)
            struct.pack_into("<Q", data, 8, random.randint(0, 2**64 - 1))
            struct.pack_into("<Q", data, 16, random.randint(0, 2**64 - 1))
            struct.pack_into("<H", data, 32, random.randint(0, 0xFFFF))
            struct.pack_into("<H", data, 42, 64)
            record = parse_log_record(bytes(data))
            if record:
                assert isinstance(record.lsn, int)

    def test_fuzz_log_record_zero_length(self):
        for _ in range(20):
            data = b"\x00" * random.randint(24, 128)
            record = parse_log_record(data)
            assert record is None or isinstance(record.lsn, int)

    def test_fuzz_log_records_many_small(self):
        for _ in range(10):
            data = os.urandom(random.randint(100, 1000))
            records = parse_log_records(data)
            # Should not loop infinitely
            assert len(records) < 100

    def test_fuzz_restart_page_random_signature(self):
        for _ in range(20):
            data = bytearray(4096)
            data[0:4] = os.urandom(4)
            header = parse_restart_page(bytes(data))
            if header:
                assert header.signature in ("RSTR",)

    def test_fuzz_log_record_boundary_conditions(self):
        for length in (47, 48, 49, 63, 64, 65):
            data = os.urandom(length)
            record = parse_log_record(data)
            if record and record.length > 0:
                assert record.length <= len(data)
