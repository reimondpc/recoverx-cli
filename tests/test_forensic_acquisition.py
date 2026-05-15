from __future__ import annotations

from datetime import datetime

from recoverx.core.acquisition.sessions import AcquisitionSession, SessionStatus
from recoverx.core.acquisition.streams import ImageStream, StreamChunk
from recoverx.core.acquisition.targets import (
    AcquisitionTarget,
    TargetMetadata,
    TargetType,
)
from recoverx.core.acquisition.transport import ChunkResult, LocalTransport


class TestAcquisitionTarget:
    def test_creation_with_path_and_type(self):
        target = AcquisitionTarget("/dev/sda", TargetType.LOCAL_DEVICE)
        assert target.path == "/dev/sda"
        assert target.target_type == TargetType.LOCAL_DEVICE

    def test_default_target_type_is_local_file(self):
        target = AcquisitionTarget("/tmp/dump.dd")
        assert target.target_type == TargetType.LOCAL_FILE

    def test_metadata_defaults(self):
        m = TargetMetadata()
        assert m.size_bytes == 0
        assert m.sector_size == 512
        assert m.filesystem == ""
        assert m.device_model == ""
        assert m.serial_number == ""
        assert m.acquired_at == ""
        assert m.hash_sha256 == ""
        assert m.notes == ""

    def test_metadata_custom_values(self):
        m = TargetMetadata(
            size_bytes=1024,
            sector_size=4096,
            filesystem="NTFS",
            device_model="Samsung SSD",
            serial_number="SN123",
            acquired_at="2025-01-01T00:00:00",
            hash_sha256="abc123",
            notes="test drive",
        )
        assert m.size_bytes == 1024
        assert m.sector_size == 4096
        assert m.filesystem == "NTFS"
        assert m.device_model == "Samsung SSD"

    def test_open_close_lifecycle(self):
        target = AcquisitionTarget("/tmp/dump.dd")
        target.open()
        d = target.to_dict()
        assert d["opened"] is True
        target.close()
        d = target.to_dict()
        assert d["opened"] is False

    def test_validate_with_empty_path(self):
        target = AcquisitionTarget("")
        issues = target.validate()
        assert "Target path is empty" in issues

    def test_validate_with_valid_path(self):
        target = AcquisitionTarget("/dev/sda")
        issues = target.validate()
        assert issues == []

    def test_to_dict_serialization(self):
        target = AcquisitionTarget("/dev/sdb", TargetType.REMOTE_DEVICE)
        d = target.to_dict()
        assert d["path"] == "/dev/sdb"
        assert d["type"] == "REMOTE_DEVICE"
        assert d["read_only"] is True
        assert d["opened"] is False
        assert "metadata" in d

    def test_is_read_only_default_is_true(self):
        target = AcquisitionTarget("/tmp/test.img")
        assert target.is_read_only is True

    def test_metadata_to_dict(self):
        m = TargetMetadata(size_bytes=2048, filesystem="FAT32")
        d = m.to_dict()
        assert d["size_bytes"] == 2048
        assert d["filesystem"] == "FAT32"
        assert d["sector_size"] == 512

    def test_metadata_is_attached_to_target(self):
        m = TargetMetadata(serial_number="SN999")
        target = AcquisitionTarget("/tmp/img", metadata=m)
        assert target.metadata.serial_number == "SN999"


class TestImageStream:
    def test_creation_with_source_and_chunk_size(self):
        stream = ImageStream("/dev/sda", chunk_size=4096)
        assert stream.source == "/dev/sda"
        assert stream.chunk_size == 4096

    def test_default_chunk_size(self):
        stream = ImageStream("/dev/sda")
        assert stream.chunk_size == 65536

    def test_read_chunk_returns_none_when_closed(self):
        stream = ImageStream("/tmp/dump.dd")
        stream.close()
        assert stream.read_chunk() is None

    def test_seek_changes_offset(self):
        stream = ImageStream("/tmp/dump.dd")
        assert stream.offset == 0
        stream.seek(1024)
        assert stream.offset == 1024
        stream.seek(0)
        assert stream.offset == 0

    def test_close_and_is_closed(self):
        stream = ImageStream("/tmp/dump.dd")
        assert stream.is_closed is False
        stream.close()
        assert stream.is_closed is True

    def test_read_chunk_returns_none_for_empty_source(self):
        stream = ImageStream("/dev/zero")
        chunk = stream.read_chunk()
        assert chunk is None

    def test_read_chunk_advances_offset(self):
        stream = ImageStream("/dev/zero", chunk_size=512)
        initial = stream.offset
        stream.read_chunk()
        assert stream.offset >= initial


class TestStreamChunk:
    def test_dataclass_properties(self):
        chunk = StreamChunk(offset=0, data=b"hello", chunk_index=0, total_chunks=10)
        assert chunk.offset == 0
        assert chunk.data == b"hello"
        assert chunk.chunk_index == 0
        assert chunk.total_chunks == 10

    def test_size_property(self):
        chunk = StreamChunk(offset=0, data=b"\xff" * 1024, chunk_index=1, total_chunks=5)
        assert chunk.size == 1024

    def test_size_zero_for_empty_data(self):
        chunk = StreamChunk(offset=0, data=b"", chunk_index=0, total_chunks=1)
        assert chunk.size == 0

    def test_to_dict(self):
        chunk = StreamChunk(offset=4096, data=b"test", chunk_index=2, total_chunks=8)
        d = chunk.to_dict()
        assert d["offset"] == 4096
        assert d["size"] == 4
        assert d["chunk_index"] == 2
        assert d["total_chunks"] == 8


class TestLocalTransport:
    def test_connect_disconnect(self):
        t = LocalTransport()
        assert t.is_connected() is False
        t.connect()
        assert t.is_connected() is True
        t.disconnect()
        assert t.is_connected() is False

    def test_send_receive_round_trip(self):
        t = LocalTransport()
        t.connect()
        result = t.send_chunk(b"hello")
        assert result.success is True
        result = t.receive_chunk()
        assert result.success is True
        assert result.data == b"hello"

    def test_send_chunk_fails_when_disconnected(self):
        t = LocalTransport()
        result = t.send_chunk(b"data")
        assert result.success is False
        assert result.error == "Not connected"

    def test_receive_chunk_fails_when_disconnected(self):
        t = LocalTransport()
        result = t.receive_chunk()
        assert result.success is False
        assert result.error == "Not connected"

    def test_receive_chunk_returns_empty_when_buffer_empty(self):
        t = LocalTransport()
        t.connect()
        result = t.receive_chunk()
        assert result.success is True
        assert result.data == b""

    def test_is_connected(self):
        t = LocalTransport()
        assert t.is_connected() is False
        t.connect()
        assert t.is_connected() is True
        t.disconnect()
        assert t.is_connected() is False

    def test_send_multiple_chunks(self):
        t = LocalTransport()
        t.connect()
        t.send_chunk(b"first")
        t.send_chunk(b"second")
        r1 = t.receive_chunk()
        r2 = t.receive_chunk()
        assert r1.data == b"first"
        assert r2.data == b"second"

    def test_disconnect_clears_buffer(self):
        t = LocalTransport()
        t.connect()
        t.send_chunk(b"data")
        t.disconnect()
        t.connect()
        result = t.receive_chunk()
        assert result.data == b""

    def test_connect_returns_true(self):
        t = LocalTransport()
        assert t.connect() is True


class TestChunkResult:
    def test_dataclass_defaults(self):
        r = ChunkResult(success=True)
        assert r.success is True
        assert r.data == b""
        assert r.error == ""
        assert r.duration_ms == 0.0
        assert r.metadata == {}

    def test_dataclass_custom_values(self):
        r = ChunkResult(
            success=False,
            data=b"partial",
            error="timeout",
            duration_ms=150.5,
            metadata={"retry": 3},
        )
        assert r.success is False
        assert r.data == b"partial"
        assert r.error == "timeout"
        assert r.duration_ms == 150.5
        assert r.metadata == {"retry": 3}


class TestAcquisitionSession:
    def test_creation_with_target(self):
        target = AcquisitionTarget("/tmp/dump.dd")
        session = AcquisitionSession(target)
        assert session.target is target
        assert session.status == SessionStatus.PENDING
        assert session.bytes_acquired == 0

    def test_session_id_is_generated(self):
        s1 = AcquisitionSession(AcquisitionTarget("/tmp/a.dd"))
        s2 = AcquisitionSession(AcquisitionTarget("/tmp/b.dd"))
        assert s1.session_id
        assert s2.session_id
        assert s1.session_id != s2.session_id

    def test_start_sets_active_and_opens_target(self):
        target = AcquisitionTarget("/tmp/dump.dd")
        session = AcquisitionSession(target)
        session.start()
        assert session.status == SessionStatus.ACTIVE
        assert target.to_dict()["opened"] is True

    def test_pause_resume(self):
        target = AcquisitionTarget("/tmp/dump.dd")
        session = AcquisitionSession(target)
        session.start()
        session.pause()
        assert session.status == SessionStatus.PAUSED
        session.resume()
        assert session.status == SessionStatus.ACTIVE

    def test_complete_sets_completed_and_closes_target(self):
        target = AcquisitionTarget("/tmp/dump.dd")
        session = AcquisitionSession(target)
        session.start()
        session.complete()
        assert session.status == SessionStatus.COMPLETED
        assert target.to_dict()["opened"] is False

    def test_fail_records_errors_and_closes_target(self):
        target = AcquisitionTarget("/tmp/dump.dd")
        session = AcquisitionSession(target)
        session.start()
        session.fail("I/O error")
        assert session.status == SessionStatus.FAILED
        d = session.to_dict()
        assert "I/O error" in d["errors"]
        assert target.to_dict()["opened"] is False

    def test_cancel_closes_target(self):
        target = AcquisitionTarget("/tmp/dump.dd")
        session = AcquisitionSession(target)
        session.start()
        session.cancel()
        assert session.status == SessionStatus.CANCELLED
        assert target.to_dict()["opened"] is False

    def test_record_bytes(self):
        target = AcquisitionTarget("/tmp/dump.dd")
        session = AcquisitionSession(target)
        session.record_bytes(1024)
        assert session.bytes_acquired == 1024
        session.record_bytes(512)
        assert session.bytes_acquired == 1536

    def test_to_dict_serialization(self):
        target = AcquisitionTarget("/tmp/dump.dd", TargetType.LOCAL_FILE)
        session = AcquisitionSession(target)
        d = session.to_dict()
        assert d["session_id"] == session.session_id
        assert d["status"] == "PENDING"
        assert d["bytes_acquired"] == 0
        assert d["target"]["path"] == "/tmp/dump.dd"
        assert d["started_at"] is None
        assert d["completed_at"] is None
        assert d["errors"] == []

    def test_to_dict_after_start(self):
        target = AcquisitionTarget("/tmp/dump.dd")
        session = AcquisitionSession(target)
        session.start()
        d = session.to_dict()
        assert d["status"] == "ACTIVE"
        assert d["started_at"] is not None
        assert d["completed_at"] is None

    def test_to_dict_after_complete(self):
        target = AcquisitionTarget("/tmp/dump.dd")
        session = AcquisitionSession(target)
        session.start()
        session.complete()
        d = session.to_dict()
        assert d["status"] == "COMPLETED"
        assert d["completed_at"] is not None

    def test_to_dict_after_fail(self):
        target = AcquisitionTarget("/tmp/dump.dd")
        session = AcquisitionSession(target)
        session.start()
        session.fail("checksum mismatch")
        d = session.to_dict()
        assert d["status"] == "FAILED"
        assert d["errors"] == ["checksum mismatch"]
