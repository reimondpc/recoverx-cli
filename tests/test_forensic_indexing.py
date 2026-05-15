from __future__ import annotations

import os
import tempfile

from recoverx.core.artifacts.models import (
    Artifact,
    DeletedArtifact,
    FileArtifact,
    HashArtifact,
    JournalArtifact,
    TimelineArtifact,
)


class TestArtifactModels:
    def test_artifact_base(self):
        a = Artifact(source="test", confidence=0.9)
        assert a.source == "test"
        assert a.confidence == 0.9
        assert len(a.artifact_id) == 16
        d = a.to_dict()
        assert d["source"] == "test"

    def test_file_artifact(self):
        fa = FileArtifact(filename="test.txt", file_size=1024, is_deleted=True)
        assert fa.filename == "test.txt"
        assert fa.is_deleted
        d = fa.to_dict()
        assert d["filename"] == "test.txt"
        assert d["is_deleted"] is True

    def test_timeline_artifact(self):
        ta = TimelineArtifact(event_type="FILE_CREATED", filename="new.txt")
        assert ta.event_type == "FILE_CREATED"
        d = ta.to_dict()
        assert d["event_type"] == "FILE_CREATED"

    def test_journal_artifact(self):
        ja = JournalArtifact(journal_type="USN", record_count=50)
        assert ja.journal_type == "USN"
        d = ja.to_dict()
        assert d["record_count"] == 50

    def test_deleted_artifact(self):
        da = DeletedArtifact(filename="gone.txt", recovery_potential="high")
        assert da.filename == "gone.txt"
        d = da.to_dict()
        assert d["recovery_potential"] == "high"

    def test_hash_artifact(self):
        ha = HashArtifact(sha256="abc123", known_duplicates=3)
        assert ha.sha256 == "abc123"
        d = ha.to_dict()
        assert d["known_duplicates"] == 3


class TestIndexEngine:
    def test_index_engine_create(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            from recoverx.core.indexing.engine import IndexEngine
            from recoverx.core.indexing.models import IndexConfig

            config = IndexConfig(db_path=db_path, read_only=False)
            engine = IndexEngine(config)
            engine.open()

            stats = engine.stats()
            assert stats.schema_version == 1
            assert stats.total_events == 0

            engine.close()
        finally:
            os.unlink(db_path)

    def test_index_engine_index_event(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            from recoverx.core.indexing.engine import IndexEngine
            from recoverx.core.indexing.models import IndexConfig
            from recoverx.core.forensics.models import ForensicEvent, EventType, EventSource

            config = IndexConfig(db_path=db_path, read_only=False)
            engine = IndexEngine(config)
            engine.open()

            event = ForensicEvent(
                timestamp=None,
                event_type=EventType.FILE_CREATED,
                source=EventSource.MFT,
                filename="test.txt",
            )
            engine.index_event(event)
            assert engine.get_event_count() >= 1

            engine.close()
        finally:
            os.unlink(db_path)

    def test_search_events(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            from recoverx.core.indexing.engine import IndexEngine
            from recoverx.core.indexing.models import IndexConfig
            from recoverx.core.forensics.models import ForensicEvent, EventType, EventSource

            config = IndexConfig(db_path=db_path, read_only=False)
            engine = IndexEngine(config)
            engine.open()

            event = ForensicEvent(
                timestamp=None,
                event_type=EventType.FILE_DELETED,
                source=EventSource.USN,
                filename="deleted.txt",
            )
            engine.index_event(event)

            results = engine.search_events(event_type="FILE_DELETED")
            assert len(results) >= 1
            assert results[0]["filename"] == "deleted.txt"

            engine.close()
        finally:
            os.unlink(db_path)

    def test_index_engine_cache(self):
        from recoverx.core.indexing.cache import BoundedCache, HitTrackingCache

        c = BoundedCache(max_size=10)
        c.set("a", 1)
        assert c.get("a") == 1
        assert c.get("b") is None
        assert c.size == 1

        hc = HitTrackingCache(max_size=10)
        hc.set("x", 100)
        assert hc.get("x") == 100
        assert hc.get("y") is None
        assert hc.hit_rate() > 0
