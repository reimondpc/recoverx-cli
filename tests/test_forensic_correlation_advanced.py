from __future__ import annotations

from datetime import datetime, timedelta

from recoverx.core.forensics.correlation import CorrelationEngine
from recoverx.core.forensics.models import EventSource, EventType, ForensicEvent


class TestAdvancedCorrelation:
    def _make_event(
        self,
        ts: datetime,
        etype: EventType,
        fname: str,
        mft: int = 1,
        parent: int = 0,
        source: EventSource = EventSource.MFT,
    ) -> ForensicEvent:
        return ForensicEvent(
            timestamp=ts,
            event_type=etype,
            source=source,
            filename=fname,
            mft_reference=mft,
            parent_mft_reference=parent,
        )

    def test_delete_recreate_detection(self):
        engine = CorrelationEngine()
        now = datetime(2026, 1, 1, 12, 0, 0)
        events = [
            self._make_event(now, EventType.FILE_DELETED, "test.txt", mft=1),
            self._make_event(
                now + timedelta(seconds=30), EventType.FILE_CREATED, "test.txt", mft=1
            ),
        ]
        result = engine._detect_delete_recreate(events)
        assert any("delete/recreate" in n.lower() for e in result for n in e.notes)

    def test_no_delete_recreate_long_gap(self):
        engine = CorrelationEngine()
        now = datetime(2026, 1, 1, 12, 0, 0)
        events = [
            self._make_event(now, EventType.FILE_DELETED, "test.txt", mft=1),
            self._make_event(now + timedelta(hours=2), EventType.FILE_CREATED, "test.txt", mft=1),
        ]
        result = engine._detect_delete_recreate(events)
        assert not any("delete/recreate" in n for e in result for n in e.notes)

    def test_parent_movement_tracking(self):
        engine = CorrelationEngine()
        now = datetime(2026, 1, 1, 12, 0, 0)
        events = [
            self._make_event(now, EventType.FILE_CREATED, "file.txt", mft=1, parent=5),
            self._make_event(
                now + timedelta(minutes=5), EventType.FILE_MODIFIED, "file.txt", mft=1, parent=10
            ),
        ]
        result = engine._track_parent_movement(events)
        assert any("Parent moved" in n for e in result for n in e.notes)

    def test_timestamp_anomaly_detection(self):
        engine = CorrelationEngine()
        now = datetime(2026, 1, 1, 12, 0, 0)
        events = [
            self._make_event(now, EventType.FILE_CREATED, "a.txt", mft=1),
            self._make_event(now - timedelta(hours=1), EventType.FILE_MODIFIED, "a.txt", mft=1),
        ]
        result = engine._detect_timestamp_anomalies(events)
        assert any("Anomalous" in n for e in result for n in e.notes)

    def test_orphan_reconstruction(self):
        engine = CorrelationEngine()
        now = datetime(2026, 1, 1, 12, 0, 0)
        events = [
            self._make_event(now, EventType.FILE_DELETED, "orphan.txt", mft=42),
        ]
        result = engine._reconstruct_orphans(events)
        assert any("orphan" in n.lower() for e in result for n in e.notes)

    def test_no_orphan_for_created_files(self):
        engine = CorrelationEngine()
        now = datetime(2026, 1, 1, 12, 0, 0)
        events = [
            self._make_event(now, EventType.FILE_CREATED, "normal.txt", mft=1),
            self._make_event(
                now + timedelta(minutes=1), EventType.FILE_DELETED, "normal.txt", mft=1
            ),
        ]
        result = engine._reconstruct_orphans(events)
        orphan_notes = [n for e in result for n in e.notes if "orphan" in n.lower()]
        assert len(orphan_notes) == 0 or "no creation" not in orphan_notes[0]

    def test_cross_source_matching(self):
        engine = CorrelationEngine()
        ts = datetime(2026, 1, 1, 12, 0, 0)
        mft_events = [
            self._make_event(ts, EventType.FILE_CREATED, "a.txt", mft=1, source=EventSource.MFT),
        ]
        usn_events = [
            self._make_event(ts, EventType.FILE_CREATED, "a.txt", mft=1, source=EventSource.USN),
        ]
        result = engine.match_mft_usn(mft_events, usn_events)
        correlated = [e for e in result if "Correlated" in "; ".join(e.notes)]
        assert len(correlated) > 0

    def test_full_correlate_pipeline(self):
        engine = CorrelationEngine()
        now = datetime(2026, 1, 1, 12, 0, 0)
        events = [
            self._make_event(now, EventType.FILE_CREATED, "a.txt", mft=1),
            self._make_event(now + timedelta(seconds=1), EventType.FILE_CREATED, "b.txt", mft=1),
        ]
        result = engine.correlate(events)
        assert len(result) >= 2
