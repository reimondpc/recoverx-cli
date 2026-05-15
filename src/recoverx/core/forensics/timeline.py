from __future__ import annotations

import csv
import json
import logging
from datetime import datetime
from io import StringIO
from typing import Any

from .models import EventSource, EventType, ForensicEvent, TimelineMetadata

logger = logging.getLogger("recoverx")


class Timeline:
    def __init__(self) -> None:
        self._events: list[ForensicEvent] = []
        self._built = False

    def add_event(self, event: ForensicEvent) -> None:
        self._events.append(event)
        self._built = False

    def add_events(self, events: list[ForensicEvent]) -> None:
        self._events.extend(events)
        self._built = False

    @property
    def events(self) -> list[ForensicEvent]:
        if not self._built:
            self._build()
        return self._events

    @property
    def metadata(self) -> TimelineMetadata:
        return self._compute_metadata()

    def _build(self) -> None:
        self._events.sort(key=lambda e: (e.timestamp or datetime.max, e.mft_reference))
        self._events = self._deduplicate(self._events)
        self._built = True

    @staticmethod
    def _deduplicate(events: list[ForensicEvent]) -> list[ForensicEvent]:
        seen: set[tuple] = set()
        result: list[ForensicEvent] = []
        for e in events:
            key = (
                e.timestamp,
                e.event_type.value,
                e.mft_reference,
                e.filename,
                e.source.value,
            )
            if key not in seen:
                seen.add(key)
                result.append(e)
        return result

    def filter(
        self,
        event_types: list[EventType] | None = None,
        sources: list[Any] | None = None,
        mft_reference: int | None = None,
        filename_contains: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        min_confidence: float = 0.0,
        deleted_only: bool = False,
    ) -> list[ForensicEvent]:
        result = self.events
        if event_types:
            result = [e for e in result if e.event_type in event_types]
        if sources:
            result = [e for e in result if e.source in sources]
        if mft_reference is not None:
            result = [e for e in result if e.mft_reference == mft_reference]
        if filename_contains:
            result = [e for e in result if filename_contains.lower() in e.filename.lower()]
        if since:
            result = [e for e in result if e.timestamp and e.timestamp >= since]
        if until:
            result = [e for e in result if e.timestamp and e.timestamp <= until]
        if min_confidence > 0.0:
            result = [e for e in result if e.confidence >= min_confidence]
        if deleted_only:
            result = [e for e in result if e.event_type in (EventType.FILE_DELETED,)]
        return result

    def filter_by_file(self, filename: str) -> list[ForensicEvent]:
        return [e for e in self.events if e.filename == filename or e.previous_filename == filename]

    def filter_by_mft(self, mft_ref: int) -> list[ForensicEvent]:
        return [e for e in self.events if e.mft_reference == mft_ref]

    def _compute_metadata(self) -> TimelineMetadata:
        events = self.events
        if not events:
            return TimelineMetadata()

        source_counts: dict[str, int] = {}
        type_counts: dict[str, int] = {}
        unique_files: set[str] = set()
        timestamps = [e.timestamp for e in events if e.timestamp is not None]

        for e in events:
            source_counts[e.source.value] = source_counts.get(e.source.value, 0) + 1
            type_counts[e.event_type.value] = type_counts.get(e.event_type.value, 0) + 1
            if e.filename:
                unique_files.add(e.filename)

        return TimelineMetadata(
            source_counts=source_counts,
            type_counts=type_counts,
            time_range_start=min(timestamps) if timestamps else None,
            time_range_end=max(timestamps) if timestamps else None,
            total_events=len(events),
            unique_files=len(unique_files),
        )

    def to_dict_list(self) -> list[dict[str, Any]]:
        return [e.to_dict() for e in self.events]

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(
            {
                "metadata": self.metadata.to_dict(),
                "events": self.to_dict_list(),
            },
            indent=indent,
        )

    def to_csv(self) -> str:
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "timestamp",
                "event_type",
                "source",
                "filename",
                "previous_filename",
                "mft_reference",
                "parent_mft_reference",
                "file_size",
                "confidence",
                "notes",
            ]
        )
        for e in self.events:
            writer.writerow(
                [
                    e.timestamp.isoformat() if e.timestamp else "",
                    e.event_type.value,
                    e.source.value,
                    e.filename,
                    e.previous_filename,
                    str(e.mft_reference),
                    str(e.parent_mft_reference),
                    str(e.file_size),
                    f"{e.confidence:.2f}",
                    "; ".join(e.notes),
                ]
            )
        return output.getvalue()

    def print_chronological(self, limit: int = 0) -> list[str]:
        lines: list[str] = []
        for i, e in enumerate(self.events):
            if limit > 0 and i >= limit:
                break
            ts = e.timestamp.strftime("%Y-%m-%d %H:%M:%S") if e.timestamp else "(no timestamp)"
            line = f"{ts} {e.event_type.value} {e.filename}"
            if e.previous_filename:
                line += f" (was: {e.previous_filename})"
            if e.source != EventSource.UNKNOWN:
                line += f" [{e.source.value}]"
            if e.confidence < 0.8:
                line += f" (confidence: {e.confidence:.2f})"
            lines.append(line)
        return lines
