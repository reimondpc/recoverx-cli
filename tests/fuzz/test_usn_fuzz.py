from __future__ import annotations

import os
import random
import struct
import tempfile

from recoverx.core.filesystems.ntfs.usn.parser import USNParser
from recoverx.core.filesystems.ntfs.usn.records import parse_usn_record, parse_usn_records
from recoverx.core.filesystems.ntfs.usn.reasons import resolve_usn_reasons
from recoverx.core.utils.raw_reader import RawReader


class TestFuzzUSNRecords:
    def test_fuzz_empty_data(self):
        for _ in range(20):
            size = random.randint(0, 128)
            data = os.urandom(size)
            records = parse_usn_records(data)
            assert isinstance(records, list)

    def test_fuzz_random_corruption(self):
        for _ in range(50):
            raw = bytearray(random.randint(24, 256))
            for i in range(len(raw)):
                raw[i] = random.randint(0, 255)
            record = parse_usn_record(bytes(raw))
            if record:
                assert isinstance(record.file_name, str)
                assert record.file_reference >= 0

    def test_fuzz_extreme_values(self):
        for _ in range(30):
            raw = bytearray(random.randint(24, 512))
            for i in range(len(raw)):
                raw[i] = random.randint(0, 255)
            try:
                struct.pack_into("<I", raw, 0, len(raw))
                struct.pack_into("<H", raw, 4, random.choice([2, 3]))
                struct.pack_into("<H", raw, 6, 0)
            except struct.error:
                continue
            record = parse_usn_record(bytes(raw))
            assert record is None or isinstance(record.file_name, str)

    def test_fuzz_oversized_filename(self):
        for _ in range(20):
            raw = bytearray(128)
            struct.pack_into("<I", raw, 0, 128)
            struct.pack_into("<H", raw, 4, 2)
            struct.pack_into("<H", raw, 6, 0)
            struct.pack_into("<H", raw, 56, 1000)
            struct.pack_into("<H", raw, 58, 60)
            record = parse_usn_record(bytes(raw))
            assert record is None or isinstance(record.file_name, str)

    def test_fuzz_zero_length_record(self):
        for _ in range(20):
            raw = b"\x00" * random.randint(24, 128)
            record = parse_usn_record(raw)
            assert record is None or isinstance(record.file_name, str)

    def test_fuzz_reason_flags(self):
        for _ in range(30):
            flag = random.randint(0, 0xFFFFFFFF)
            reasons = resolve_usn_reasons(flag)
            assert isinstance(reasons, list)
            assert all(isinstance(r, str) for r in reasons)


class TestFuzzUSNParser:
    def test_fuzz_invalid_bpb(self):
        for _ in range(10):
            tmp = tempfile.NamedTemporaryFile(suffix=".img", delete=False)
            try:
                sector = bytearray(512)
                sector[3:11] = b"NTFS    "
                struct.pack_into("<H", sector, 11, 512)
                sector[13] = 1
                struct.pack_into("<Q", sector, 40, 65536)
                struct.pack_into("<Q", sector, 48, 16)
                struct.pack_into("<I", sector, 56, 8)
                sector[510] = 0x55
                sector[511] = 0xAA
                tmp.write(bytes(sector))
                tmp.flush()

                class FakeBPB:
                    cluster_size = 512
                    bytes_per_file_record = 1024
                    mft_byte_offset = 65536

                reader = RawReader(tmp.name)
                reader.open()
                try:
                    parser = USNParser(reader, FakeBPB())
                    result = parser.parse_raw()
                    assert isinstance(result, list)
                finally:
                    reader.close()
            finally:
                os.unlink(tmp.name)
