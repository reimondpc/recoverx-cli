from __future__ import annotations

import os
import struct
import tempfile

from recoverx.core.filesystems.ntfs.boot_sector import parse_boot_sector
from recoverx.core.filesystems.ntfs.recovery import NTFSRecovery
from recoverx.core.filesystems.ntfs.structures import (
    NTFSBootSector,
    NonResidentAttribute,
    MFTRecord,
    MFTRecordHeader,
)
from recoverx.core.utils.raw_reader import RawReader


def _make_bpb() -> NTFSBootSector:
    return NTFSBootSector(
        bytes_per_sector=512,
        sectors_per_cluster=1,
        total_sectors=65536,
        mft_cluster=16,
        clusters_per_file_record=0xF6,
    )


def _make_reader(data: bytes) -> RawReader:
    f = tempfile.NamedTemporaryFile(delete=False)
    f.write(data)
    f.close()
    reader = RawReader(f.name)
    reader.open()
    return reader


def _make_non_resident_record(
    runs: list[tuple[int, int]],
    real_size: int,
    content: bytes,
    deleted: bool = False,
) -> MFTRecord:
    header = MFTRecordHeader(
        signature="FILE",
        flags=0x0000 if deleted else 0x0001,
        mft_record_number=10,
        attrs_offset=48,
        used_size=48 + 64 + sum(c for c, _ in runs) * 2 + 64,
    )

    nr = NonResidentAttribute(
        attr_type=0x80,
        attr_type_name="DATA",
        non_resident=True,
        starting_vcn=0,
        last_vcn=sum(c for c, _ in runs) - 1,
        runlist_offset=64,
        real_size=real_size,
        allocated_size=sum(c for c, _ in runs) * 512,
        initialised_size=real_size,
        data_runs=[{"cluster_count": c, "cluster_offset": o, "is_sparse": False} for c, o in runs],
    )

    record = MFTRecord(
        header=header,
        resident=False,
        data_non_resident=nr,
    )

    return record


class TestNonResidentRecovery:
    def test_recover_simple_non_resident(self):
        data = b"NTFS_NON_RESIDENT_TEST_DATA!" * 50
        bpb = _make_bpb()
        reader = _make_reader(data)
        try:
            rec = NTFSRecovery(reader, bpb)
            runs = [{"cluster_count": 5, "cluster_offset": 0, "is_sparse": False}]
            nr = NonResidentAttribute(
                attr_type=0x80,
                non_resident=True,
                starting_vcn=0,
                last_vcn=4,
                runlist_offset=64,
                real_size=500,
                allocated_size=5 * 512,
                initialised_size=500,
                data_runs=runs,
            )
            record = MFTRecord(
                header=MFTRecordHeader(signature="FILE", flags=0x0001, mft_record_number=5),
                resident=False,
                data_non_resident=nr,
            )
            result = rec.recover_non_resident_file(record)
            assert result.resident is False
            assert result.recovery_status == "recovered"
            assert len(result.data) == 500
            assert result.data == data[:500]
            assert result.sha256 is not None
        finally:
            reader.close()
            os.unlink(reader.path)

    def test_recover_fragmented(self):
        chunk1 = b"AAAA" * 128
        chunk2 = b"BBBB" * 128
        chunk3 = b"CCCC" * 128
        data = chunk1 + chunk2 + chunk3
        bpb = _make_bpb()
        reader = _make_reader(data)
        try:
            rec = NTFSRecovery(reader, bpb)
            runs = [
                {"cluster_count": 1, "cluster_offset": 0, "is_sparse": False},
                {"cluster_count": 1, "cluster_offset": 1, "is_sparse": False},
                {"cluster_count": 1, "cluster_offset": 1, "is_sparse": False},
            ]
            nr = NonResidentAttribute(
                attr_type=0x80,
                non_resident=True,
                starting_vcn=0,
                last_vcn=2,
                runlist_offset=64,
                real_size=1536,
                allocated_size=3 * 512,
                initialised_size=1536,
                data_runs=runs,
            )
            record = MFTRecord(
                header=MFTRecordHeader(signature="FILE", flags=0x0001, mft_record_number=5),
                resident=False,
                data_non_resident=nr,
            )
            result = rec.recover_non_resident_file(record)
            assert result.recovery_status == "recovered"
            assert len(result.data) == 1536
            assert result.fragmented
            assert result.run_count == 3
        finally:
            reader.close()
            os.unlink(reader.path)

    def test_recover_sparse(self):
        data = b"X" * 1024
        bpb = _make_bpb()
        reader = _make_reader(data)
        try:
            rec = NTFSRecovery(reader, bpb)
            runs = [
                {"cluster_count": 1, "cluster_offset": 0, "is_sparse": False},
                {"cluster_count": 3, "cluster_offset": 0, "is_sparse": True},
                {"cluster_count": 1, "cluster_offset": 2, "is_sparse": False},
            ]
            nr = NonResidentAttribute(
                attr_type=0x80,
                non_resident=True,
                starting_vcn=0,
                last_vcn=4,
                runlist_offset=64,
                real_size=5 * 512,
                allocated_size=2 * 512,
                initialised_size=5 * 512,
                data_runs=runs,
            )
            record = MFTRecord(
                header=MFTRecordHeader(signature="FILE", flags=0x0001, mft_record_number=5),
                resident=False,
                data_non_resident=nr,
            )
            result = rec.recover_non_resident_file(record)
            assert result.recovery_status == "recovered"
            assert result.sparse
            assert result.data[:512] == data[:512]
            assert result.data[512:2048] == b"\x00" * 1536
        finally:
            reader.close()
            os.unlink(reader.path)

    def test_recover_deleted_non_resident(self):
        data = b"DELETED_NON_RESIDENT_FILE" * 32
        bpb = _make_bpb()
        reader = _make_reader(data)
        try:
            rec = NTFSRecovery(reader, bpb)
            record = _make_non_resident_record([(1, 0)], len(data), data, deleted=True)
            record.header.flags = 0x0000
            result = rec.recover_non_resident_file(record)
            assert result.recovery_status == "recovered"
            assert result.deleted
            assert "deleted" in result.recovery_notes[0].lower()
        finally:
            reader.close()
            os.unlink(reader.path)

    def test_no_non_resident_data(self):
        bpb = _make_bpb()
        record = MFTRecord(
            header=MFTRecordHeader(signature="FILE", flags=0x0001, mft_record_number=5),
            resident=True,
            data_resident=b"hello",
        )
        with tempfile.NamedTemporaryFile() as f:
            f.write(b"x" * 4096)
            f.flush()
            reader = RawReader(f.name)
            reader.open()
            try:
                rec = NTFSRecovery(reader, bpb)
                result = rec.recover_non_resident_file(record)
                assert result.recovery_status == "no_non_resident_data"
            finally:
                reader.close()

    def test_classify_recoverable(self):
        data = b"X" * 5120
        bpb = _make_bpb()
        reader = _make_reader(data)
        try:
            rec = NTFSRecovery(reader, bpb)
            record = _make_non_resident_record([(10, 0)], 5120, data)
            status = rec.classify_recoverability(record)
            assert status == "recoverable"
        finally:
            reader.close()
            os.unlink(reader.path)

    def test_classify_corrupted(self):
        bpb = _make_bpb()
        reader = _make_reader(b"X" * 512)
        try:
            rec = NTFSRecovery(reader, bpb)
            record = _make_non_resident_record([(10, 0)], 5120, b"X" * 512)
            status = rec.classify_recoverability(record)
            assert status in ("corrupted", "partially_recoverable")
        finally:
            reader.close()
            os.unlink(reader.path)

    def test_find_non_resident_files(self):
        bpb = _make_bpb()

        class FakeRecord(MFTRecord):
            pass

        with tempfile.NamedTemporaryFile() as f:
            f.write(b"\x00" * (1024 * 512))
            f.flush()
            reader = RawReader(f.name)
            reader.open()
            try:
                rec = NTFSRecovery(reader, bpb)
                records = rec.find_non_resident_files(max_records=10)
                assert isinstance(records, list)
            finally:
                reader.close()

    def test_analyse_runs(self):
        data = b"X" * 5120
        bpb = _make_bpb()
        reader = _make_reader(data)
        try:
            rec = NTFSRecovery(reader, bpb)
            record = _make_non_resident_record([(10, 0)], 5120, data)
            analysis = rec.analyse_runs(record)
            assert analysis["has_runs"]
            assert analysis["run_count"] == 1
            assert analysis["real_size"] == 5120
            assert not analysis["is_fragmented"]
            assert not analysis["is_sparse"]
        finally:
            reader.close()
            os.unlink(reader.path)

    def test_analyse_fragmented_runs(self):
        data = b"X" * (512 * 10)
        bpb = _make_bpb()
        reader = _make_reader(data)
        try:
            rec = NTFSRecovery(reader, bpb)
            run_list = [
                {"cluster_count": 3, "cluster_offset": 0, "is_sparse": False},
                {"cluster_count": 4, "cluster_offset": 3, "is_sparse": False},
                {"cluster_count": 3, "cluster_offset": 4, "is_sparse": False},
            ]
            nr = NonResidentAttribute(
                attr_type=0x80,
                non_resident=True,
                starting_vcn=0,
                last_vcn=9,
                runlist_offset=64,
                real_size=10 * 512,
                allocated_size=10 * 512,
                initialised_size=10 * 512,
                data_runs=run_list,
            )
            record = MFTRecord(
                header=MFTRecordHeader(signature="FILE", flags=0x0001, mft_record_number=5),
                resident=False,
                data_non_resident=nr,
            )
            analysis = rec.analyse_runs(record)
            assert analysis["has_runs"]
            assert analysis["run_count"] == 3
            assert analysis["is_fragmented"]
        finally:
            reader.close()
            os.unlink(reader.path)

    def test_recover_file_integrity(self):
        original = b"INTEGRITY_CHECK_" * 100 + b"TAIL_MARKER_12345"
        data = original
        bpb = _make_bpb()
        reader = _make_reader(data)
        try:
            rec = NTFSRecovery(reader, bpb)
            record = _make_non_resident_record(
                [(5, 0)],
                len(original),
                original,
            )
            result = rec.recover_non_resident_file(record)
            assert result.data == original
        finally:
            reader.close()
            os.unlink(reader.path)


class TestNonResidentNTFSRecoveryWithImage:
    def test_recover_via_walk(self):
        with tempfile.NamedTemporaryFile(suffix=".img", delete=False) as f:
            sector = bytearray(512)
            sector[0:3] = b"\xeb\x52\x90"
            sector[3:11] = b"NTFS    "
            struct.pack_into("<H", sector, 11, 512)
            sector[13] = 1
            struct.pack_into("<Q", sector, 40, 65536)
            struct.pack_into("<Q", sector, 48, 16)
            struct.pack_into("<Q", sector, 56, 8)
            sector[64] = 0xF6
            sector[68] = 0x01
            sector[66] = 0x29
            struct.pack_into("<Q", sector, 72, 0xA1B2C3D4E5F6)
            sector[510] = 0x55
            sector[511] = 0xAA
            f.write(bytes(sector))
            f.write(b"\x00" * (16 * 512 - 512))
            for i in range(20):
                f.write(b"\x00" * 48)
                f.write(b"FILE")
                f.write(struct.pack("<H", 48))
                f.write(struct.pack("<H", 2))
                f.write(struct.pack("<Q", 0))
                f.write(struct.pack("<H", 0))
                f.write(struct.pack("<H", 0))
                f.write(struct.pack("<H", 48))
                f.write(struct.pack("<H", 0x0001))
                f.write(struct.pack("<I", 1024))
                f.write(struct.pack("<I", 1024))
                f.write(b"\x00" * 12)
                f.write(struct.pack("<I", i))
                f.write(b"\x00" * (1024 - 48))
            f.flush()
            img_path = f.name

        reader = RawReader(img_path)
        reader.open()
        try:
            bpb_read = parse_boot_sector(reader.read_at(0, 512))
            assert bpb_read is not None
            rec = NTFSRecovery(reader, bpb_read)
            records = rec.walk_mft(max_records=10)
            assert isinstance(records, list)
        finally:
            reader.close()
            os.unlink(img_path)
