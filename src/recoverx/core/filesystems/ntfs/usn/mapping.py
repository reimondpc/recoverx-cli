from __future__ import annotations

from datetime import datetime, timezone

from recoverx.core.forensics.events import (
    attribute_changed,
    file_created,
    file_deleted,
    file_modified,
    make_event,
)
from recoverx.core.forensics.models import (
    Confidence,
    EventSource,
    EventType,
    ForensicEvent,
)

from .records import USNRecord


def usn_to_event(record: USNRecord) -> ForensicEvent:
    ts = record.timestamp or datetime.now(timezone.utc)
    filename = record.file_name
    mft_ref = record.file_reference
    parent_ref = record.parent_reference

    reason_names = record.reason_names
    reasons_int = record.reason_flags

    flags: list[str] = [n.replace("USN_REASON_", "") for n in reason_names]

    created = bool(reasons_int & 0x00000100)
    deleted = bool(reasons_int & 0x00000200)
    renamed_old = bool(reasons_int & 0x00001000)
    renamed_new = bool(reasons_int & 0x00002000)
    modified = bool(reasons_int & 0x00000001 | reasons_int & 0x00000002 | reasons_int & 0x00000004)
    overwritten = bool(reasons_int & 0x00000001)
    truncated = bool(reasons_int & 0x00000004)
    security = bool(reasons_int & 0x00000800)
    ea = bool(reasons_int & 0x00000400)
    basic_info = bool(reasons_int & 0x00008000)
    close = bool(reasons_int & 0x80000000)

    event: ForensicEvent | None = None

    if created:
        event = file_created(
            ts, filename, mft_ref, parent_ref,
            source=EventSource.USN,
        )
    elif deleted and not close:
        event = file_deleted(
            ts, filename, mft_ref, parent_ref,
            source=EventSource.USN,
        )
    elif renamed_old:
        event = make_event(
            EventType.FILE_RENAMED, EventSource.USN, ts,
            filename=filename, mft_reference=mft_ref,
            previous_filename="(old name)",  # corrected on RENAME_NEW
            parent_mft_reference=parent_ref,
            confidence=Confidence.HIGH.value,
        )
    elif renamed_new:
        event = make_event(
            EventType.FILE_RENAMED, EventSource.USN, ts,
            filename=filename, mft_reference=mft_ref,
            confidence=Confidence.HIGH.value,
            parent_mft_reference=parent_ref,
        )
    elif modified:
        event = file_modified(
            ts, filename, mft_ref,
            source=EventSource.USN,
        )
    elif security:
        event = attribute_changed(
            ts, filename, mft_ref,
            attribute_type="SECURITY_DESCRIPTOR",
            source=EventSource.USN,
        )
    elif basic_info:
        event = attribute_changed(
            ts, filename, mft_ref,
            attribute_type="BASIC_INFO",
            source=EventSource.USN,
        )
    elif ea:
        event = attribute_changed(
            ts, filename, mft_ref,
            attribute_type="EA",
            source=EventSource.USN,
        )
    elif overwritten:
        event = make_event(
            EventType.FILE_OVERWRITTEN, EventSource.USN, ts,
            filename=filename, mft_reference=mft_ref,
            parent_mft_reference=parent_ref,
            confidence=Confidence.MEDIUM.value,
        )
    elif truncated:
        event = make_event(
            EventType.FILE_TRUNCATED, EventSource.USN, ts,
            filename=filename, mft_reference=mft_ref,
            parent_mft_reference=parent_ref,
            confidence=Confidence.MEDIUM.value,
        )
    else:
        event = make_event(
            EventType.JOURNAL_ENTRY, EventSource.USN, ts,
            filename=filename, mft_reference=mft_ref,
            parent_mft_reference=parent_ref,
            confidence=Confidence.LOW.value,
            usn_reason_flags=",".join(reason_names),
        )

    event.usn_reason_flags = flags
    event.lsn = record.usn
    event.source_record = record.to_dict()
    event.notes.append(f"USN v{record.major_version}.{record.minor_version}")
    if close:
        event.notes.append("Handle closed")

    return event


def map_usn_records(records: list[USNRecord]) -> list[ForensicEvent]:
    events: list[ForensicEvent] = []
    rename_pairs: dict[int, tuple[USNRecord, int]] = {}

    for record in records:
        if record.reason_flags & 0x00001000:
            rename_pairs[record.file_reference] = (record, record.raw_offset)
        elif record.reason_flags & 0x00002000:
            old_entry = rename_pairs.pop(record.file_reference, None)
            if old_entry:
                old_event = usn_to_event(old_entry[0])
                new_event = usn_to_event(record)
                new_event.previous_filename = old_event.filename
                events.append(old_event)
                events.append(new_event)
                continue

        event = usn_to_event(record)
        events.append(event)

    for _, (record, _) in rename_pairs.items():
        events.append(usn_to_event(record))

    return events
