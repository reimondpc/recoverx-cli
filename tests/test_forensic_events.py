from __future__ import annotations

from datetime import datetime, timezone

from recoverx.core.forensics.artifacts import (
    activity_summary,
    extract_deletion_chain,
    extract_rename_chain,
    most_active_files,
)
from recoverx.core.forensics.correlation import CorrelationEngine
from recoverx.core.forensics.events import (
    attribute_changed,
    file_created,
    file_deleted,
    file_modified,
    file_renamed,
    make_event,
)
from recoverx.core.forensics.models import (
    Confidence,
    EventSource,
    EventType,
    ForensicEvent,
)
from recoverx.core.forensics.timeline import Timeline


def test_event_type_enum():
    assert EventType.FILE_CREATED.value == "FILE_CREATED"
    assert EventType.FILE_DELETED.value == "FILE_DELETED"
    assert EventType.FILE_MODIFIED.value == "FILE_MODIFIED"
    assert EventType.FILE_RENAMED.value == "FILE_RENAMED"


def test_event_source_enum():
    assert EventSource.MFT.value == "MFT"
    assert EventSource.USN.value == "USN"
    assert EventSource.LOGFILE.value == "LOGFILE"


def test_confidence_levels():
    assert Confidence.CERTAIN.value == 1.0
    assert Confidence.HIGH.value == 0.95
    assert Confidence.from_score(0.96) == Confidence.CERTAIN
    assert Confidence.from_score(0.90) == Confidence.HIGH
    assert Confidence.from_score(0.75) == Confidence.MEDIUM
    assert Confidence.from_score(0.55) == Confidence.LOW
    assert Confidence.from_score(0.35) == Confidence.SPECULATIVE
    assert Confidence.from_score(0.10) == Confidence.GUESS


def test_forensic_event_creation():
    ts = datetime.now(timezone.utc)
    event = ForensicEvent(
        timestamp=ts,
        event_type=EventType.FILE_CREATED,
        source=EventSource.MFT,
        filename="test.txt",
        mft_reference=45,
    )
    assert event.event_type == EventType.FILE_CREATED
    assert event.filename == "test.txt"
    assert event.mft_reference == 45


def test_event_factory_functions():
    ts = datetime.now(timezone.utc)
    c = file_created(ts, "new.txt", mft_reference=10)
    assert c.event_type == EventType.FILE_CREATED
    assert c.filename == "new.txt"
    assert c.mft_reference == 10
    assert c.source == EventSource.MFT

    d = file_deleted(ts, "old.txt", mft_reference=20)
    assert d.event_type == EventType.FILE_DELETED
    assert d.filename == "old.txt"

    m = file_modified(ts, "edit.txt", mft_reference=30, file_size=100)
    assert m.event_type == EventType.FILE_MODIFIED
    assert m.file_size == 100

    r = file_renamed(ts, "old.txt", "new.txt", mft_reference=40)
    assert r.event_type == EventType.FILE_RENAMED
    assert r.previous_filename == "old.txt"
    assert r.filename == "new.txt"

    a = attribute_changed(ts, "sec.txt", mft_reference=50, attribute_type="SECURITY")
    assert a.event_type == EventType.ATTRIBUTE_CHANGED


def test_event_to_dict():
    ts = datetime(2026, 5, 14, 10, 0, 0, tzinfo=timezone.utc)
    event = file_created(ts, "report.docx", mft_reference=100, parent_mft_reference=5)
    d = event.to_dict()
    assert d["timestamp"] == "2026-05-14T10:00:00+00:00"
    assert d["event_type"] == "FILE_CREATED"
    assert d["filename"] == "report.docx"
    assert d["mft_reference"] == 100


def test_timeline_add_and_sort():
    tl = Timeline()
    ts1 = datetime(2026, 5, 14, 10, 0, 0, tzinfo=timezone.utc)
    ts2 = datetime(2026, 5, 14, 9, 0, 0, tzinfo=timezone.utc)
    tl.add_event(file_created(ts1, "later.txt"))
    tl.add_event(file_created(ts2, "earlier.txt"))
    events = tl.events
    assert events[0].filename == "earlier.txt"
    assert events[1].filename == "later.txt"


def test_timeline_deduplication():
    tl = Timeline()
    ts = datetime(2026, 5, 14, 10, 0, 0, tzinfo=timezone.utc)
    tl.add_event(file_created(ts, "dup.txt", mft_reference=1))
    tl.add_event(file_created(ts, "dup.txt", mft_reference=1))
    assert len(tl.events) == 1


def test_timeline_filter():
    tl = Timeline()
    ts = datetime(2026, 5, 14, 10, 0, 0, tzinfo=timezone.utc)
    tl.add_event(file_created(ts, "a.txt"))
    tl.add_event(file_deleted(ts, "b.txt"))
    deleted = tl.filter(event_types=[EventType.FILE_DELETED])
    assert len(deleted) == 1
    assert deleted[0].filename == "b.txt"


def test_timeline_metadata():
    tl = Timeline()
    ts = datetime(2026, 5, 14, 10, 0, 0, tzinfo=timezone.utc)
    tl.add_event(file_created(ts, "a.txt"))
    tl.add_event(file_deleted(ts, "b.txt"))
    meta = tl.metadata
    assert meta.total_events == 2
    assert meta.type_counts.get("FILE_CREATED") == 1
    assert meta.type_counts.get("FILE_DELETED") == 1


def test_timeline_csv_output():
    tl = Timeline()
    ts = datetime(2026, 5, 14, 10, 0, 0, tzinfo=timezone.utc)
    tl.add_event(file_created(ts, "test.csv"))
    csv = tl.to_csv()
    assert "timestamp" in csv
    assert "FILE_CREATED" in csv
    assert "test.csv" in csv


def test_correlation_engine_rename():
    engine = CorrelationEngine()
    ts = datetime(2026, 5, 14, 10, 0, 0, tzinfo=timezone.utc)
    events = [
        file_created(ts, "draft.docx", mft_reference=1),
        file_modified(ts, "draft.docx", mft_reference=1),
    ]
    correlated = engine.correlate(events)
    assert len(correlated) >= 2


def test_correlation_dedup():
    engine = CorrelationEngine()
    ts = datetime(2026, 5, 14, 10, 0, 0, tzinfo=timezone.utc)
    events = [
        file_created(ts, "f.txt", mft_reference=1),
        file_created(ts, "f.txt", mft_reference=1),
    ]
    result = engine.correlate(events)
    assert len(result) == 1


def test_activity_summary():
    ts = datetime(2026, 5, 14, 10, 0, 0, tzinfo=timezone.utc)
    events = [
        file_created(ts, "a.txt"),
        file_deleted(ts, "b.txt"),
        file_modified(ts, "c.txt"),
        file_renamed(ts, "old", "new"),
    ]
    summary = activity_summary(events)
    assert summary["creates"] == 1
    assert summary["deletes"] == 1
    assert summary["modifies"] == 1
    assert summary["renames"] == 1


def test_most_active_files():
    ts = datetime(2026, 5, 14, 10, 0, 0, tzinfo=timezone.utc)
    events = [
        file_created(ts, "active.txt"),
        file_modified(ts, "active.txt"),
        file_modified(ts, "active.txt"),
        file_created(ts, "quiet.txt"),
    ]
    top = most_active_files(events, top_n=2)
    assert top[0][0] == "active.txt"
    assert top[0][1] == 3


def test_extract_rename_chain():
    ts = datetime(2026, 5, 14, 10, 0, 0, tzinfo=timezone.utc)
    events = [
        file_renamed(ts, "old", "new", mft_reference=1),
        file_deleted(ts, "gone.txt"),
    ]
    renames = extract_rename_chain(events)
    assert len(renames) == 1
    assert renames[0].previous_filename == "old"


def test_make_event_with_kwargs():
    ts = datetime(2026, 5, 14, 10, 0, 0, tzinfo=timezone.utc)
    event = make_event(
        EventType.JOURNAL_ENTRY,
        EventSource.LOGFILE,
        ts,
        filename="log.dat",
        notes=["Test note"],
    )
    assert event.event_type == EventType.JOURNAL_ENTRY
    assert event.source == EventSource.LOGFILE
    assert "Test note" in event.notes


def test_event_ordering():
    ts1 = datetime(2026, 5, 14, 9, 0, 0, tzinfo=timezone.utc)
    ts2 = datetime(2026, 5, 14, 10, 0, 0, tzinfo=timezone.utc)
    e1 = file_created(ts1, "first.txt")
    e2 = file_created(ts2, "second.txt")
    assert e1 < e2


def test_timeline_filter_by_mft():
    tl = Timeline()
    ts = datetime(2026, 5, 14, 10, 0, 0, tzinfo=timezone.utc)
    tl.add_event(file_created(ts, "f1.txt", mft_reference=10))
    tl.add_event(file_created(ts, "f2.txt", mft_reference=20))
    filtered = tl.filter_by_mft(10)
    assert len(filtered) == 1
    assert filtered[0].filename == "f1.txt"


def test_timeline_filter_by_file():
    tl = Timeline()
    ts = datetime(2026, 5, 14, 10, 0, 0, tzinfo=timezone.utc)
    tl.add_event(file_renamed(ts, "old_name.txt", "new_name.txt", mft_reference=5))
    by_old = tl.filter_by_file("old_name.txt")
    assert len(by_old) == 1
    by_new = tl.filter_by_file("new_name.txt")
    assert len(by_new) == 1


def test_correlation_mft_usn_matching():
    engine = CorrelationEngine()
    ts = datetime(2026, 5, 14, 10, 0, 0, tzinfo=timezone.utc)
    mft_events = [file_created(ts, "f.txt", mft_reference=1)]
    usn_events = [file_created(ts, "f.txt", mft_reference=1)]
    matched = engine.match_mft_usn(mft_events, usn_events)
    assert any(e.confidence == Confidence.HIGH.value for e in matched)


def test_confidence_from_score():
    assert Confidence.from_score(1.0) == Confidence.CERTAIN
    assert Confidence.from_score(0.0) == Confidence.GUESS
    assert Confidence.from_score(0.5) == Confidence.LOW
    assert Confidence.from_score(0.7) == Confidence.MEDIUM


def test_timeline_chronological_print():
    tl = Timeline()
    ts = datetime(2026, 5, 14, 10, 0, 0, tzinfo=timezone.utc)
    tl.add_event(file_created(ts, "print_test.txt"))
    lines = tl.print_chronological(limit=5)
    assert len(lines) == 1
    assert "FILE_CREATED" in lines[0]
    assert "print_test.txt" in lines[0]


def test_extract_deletion_chain():
    ts = datetime(2026, 5, 14, 10, 0, 0, tzinfo=timezone.utc)
    events = [
        file_deleted(ts, "old.txt", mft_reference=1),
        file_deleted(ts, "gone.txt", mft_reference=2),
        file_created(ts, "new.txt"),
    ]
    deletions = extract_deletion_chain(events)
    assert len(deletions) == 2
    assert deletions[0].event_type == EventType.FILE_DELETED
