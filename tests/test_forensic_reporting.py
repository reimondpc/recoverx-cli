from __future__ import annotations

from datetime import datetime

from recoverx.core.forensics.models import EventSource, EventType, ForensicEvent
from recoverx.core.forensics.reporting import (
    events_to_csv,
    events_to_json,
    events_to_markdown,
    investigation_summary,
)


class TestForensicReporting:
    def test_events_to_csv(self):
        events = [
            ForensicEvent(
                timestamp=datetime(2026, 1, 1, 12, 0, 0),
                event_type=EventType.FILE_CREATED,
                source=EventSource.MFT,
                filename="test.txt",
                file_size=100,
            )
        ]
        csv = events_to_csv(events)
        assert "FILE_CREATED" in csv
        assert "test.txt" in csv
        assert "timestamp" in csv

    def test_events_to_json(self):
        events = [
            ForensicEvent(
                timestamp=datetime(2026, 1, 1),
                event_type=EventType.FILE_DELETED,
                source=EventSource.USN,
                filename="gone.txt",
            )
        ]
        data = events_to_json(events)
        assert "FILE_DELETED" in data
        assert "gone.txt" in data
        assert "forensic_timeline" in data

    def test_events_to_markdown(self):
        events = [
            ForensicEvent(
                timestamp=datetime(2026, 1, 1),
                event_type=EventType.FILE_RENAMED,
                source=EventSource.USN,
                filename="new.txt",
                previous_filename="old.txt",
            )
        ]
        md = events_to_markdown(events, "Test Report")
        assert "Test Report" in md
        assert "FILE_RENAMED" in md
        assert "old.txt" in md

    def test_events_to_markdown_empty(self):
        md = events_to_markdown([], "Empty Report")
        assert "Empty Report" in md
        assert "No events" in md

    def test_investigation_summary(self):
        events = [
            ForensicEvent(
                timestamp=datetime(2026, 1, 1),
                event_type=EventType.FILE_CREATED,
                source=EventSource.MFT,
                filename="a.txt",
            ),
            ForensicEvent(
                timestamp=datetime(2026, 1, 2),
                event_type=EventType.FILE_DELETED,
                source=EventSource.USN,
                filename="a.txt",
            ),
            ForensicEvent(
                timestamp=datetime(2026, 1, 3),
                event_type=EventType.FILE_RENAMED,
                source=EventSource.USN,
                filename="b.txt",
                previous_filename="a.txt",
            ),
        ]
        s = investigation_summary(events)
        assert s["total_events"] == 3
        assert s["created_count"] == 1
        assert s["deleted_count"] == 1
        assert s["renamed_count"] == 1
        assert s["unique_files"] >= 1

    def test_investigation_summary_empty(self):
        s = investigation_summary([])
        assert s["total_events"] == 0
