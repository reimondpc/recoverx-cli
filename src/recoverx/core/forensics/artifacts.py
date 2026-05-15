from __future__ import annotations

from .models import EventType, ForensicEvent


def extract_rename_chain(events: list[ForensicEvent]) -> list[ForensicEvent]:
    renames = [e for e in events if e.event_type == EventType.FILE_RENAMED]
    renames.sort(key=lambda e: e.timestamp or e.mft_reference)
    return renames


def extract_deletion_chain(events: list[ForensicEvent]) -> list[ForensicEvent]:
    deletions = [e for e in events if e.event_type == EventType.FILE_DELETED]
    deletions.sort(key=lambda e: e.timestamp or e.mft_reference)
    return deletions


def file_lifespan(events: list[ForensicEvent], filename: str) -> list[ForensicEvent]:
    return [e for e in events if e.filename == filename or e.previous_filename == filename]


def activity_summary(events: list[ForensicEvent]) -> dict:
    creates = sum(1 for e in events if e.event_type == EventType.FILE_CREATED)
    deletes = sum(1 for e in events if e.event_type == EventType.FILE_DELETED)
    modifies = sum(1 for e in events if e.event_type == EventType.FILE_MODIFIED)
    renames = sum(1 for e in events if e.event_type == EventType.FILE_RENAMED)
    return {
        "total_events": len(events),
        "creates": creates,
        "deletes": deletes,
        "modifies": modifies,
        "renames": renames,
        "ratio_create_delete": f"{creates/deletes:.2f}" if deletes else "inf",
    }


def most_active_files(
    events: list[ForensicEvent],
    top_n: int = 10,
) -> list[tuple[str, int]]:
    counter: dict[str, int] = {}
    for e in events:
        if e.filename:
            counter[e.filename] = counter.get(e.filename, 0) + 1
    sorted_files = sorted(counter.items(), key=lambda x: -x[1])
    return sorted_files[:top_n]
