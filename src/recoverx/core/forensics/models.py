from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class EventType(str, Enum):
    FILE_CREATED = "FILE_CREATED"
    FILE_DELETED = "FILE_DELETED"
    FILE_MODIFIED = "FILE_MODIFIED"
    FILE_RENAMED = "FILE_RENAMED"
    FILE_MOVED = "FILE_MOVED"
    FILE_TRUNCATED = "FILE_TRUNCATED"
    FILE_OVERWRITTEN = "FILE_OVERWRITTEN"
    ATTRIBUTE_CHANGED = "ATTRIBUTE_CHANGED"
    SECURITY_CHANGED = "SECURITY_CHANGED"
    MFT_CHANGED = "MFT_CHANGED"
    JOURNAL_ENTRY = "JOURNAL_ENTRY"
    INDEX_ENTRY = "INDEX_ENTRY"
    LOGFILE_RECORD = "LOGFILE_RECORD"
    UNKNOWN = "UNKNOWN"


class EventSource(str, Enum):
    MFT = "MFT"
    USN = "USN"
    LOGFILE = "LOGFILE"
    TIMELINE = "TIMELINE"
    CORRELATION = "CORRELATION"
    UNKNOWN = "UNKNOWN"


class Confidence(float, Enum):
    CERTAIN = 1.0
    HIGH = 0.95
    MEDIUM = 0.80
    LOW = 0.60
    SPECULATIVE = 0.40
    GUESS = 0.20

    @classmethod
    def from_score(cls, score: float) -> Confidence:
        if score >= 0.95:
            return cls.CERTAIN
        if score >= 0.85:
            return cls.HIGH
        if score >= 0.70:
            return cls.MEDIUM
        if score >= 0.50:
            return cls.LOW
        if score >= 0.30:
            return cls.SPECULATIVE
        return cls.GUESS


@dataclass
class ForensicEvent:
    timestamp: datetime | None
    event_type: EventType
    source: EventSource
    filename: str = ""
    parent_name: str = ""
    mft_reference: int = 0
    parent_mft_reference: int = 0
    previous_filename: str = ""
    file_size: int = 0
    attributes: dict[str, Any] = field(default_factory=dict)
    confidence: float = Confidence.MEDIUM.value
    notes: list[str] = field(default_factory=list)
    usn_reason_flags: list[str] = field(default_factory=list)
    lsn: int = 0
    source_record: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "event_type": self.event_type.value,
            "source": self.source.value,
            "filename": self.filename,
            "parent_name": self.parent_name,
            "mft_reference": self.mft_reference,
            "parent_mft_reference": self.parent_mft_reference,
            "previous_filename": self.previous_filename,
            "file_size": self.file_size,
            "confidence": round(self.confidence, 2),
            "notes": self.notes,
            "usn_reason_flags": self.usn_reason_flags,
            "lsn": self.lsn,
        }

    def __lt__(self, other: ForensicEvent) -> bool:
        if self.timestamp and other.timestamp:
            return self.timestamp < other.timestamp
        if self.timestamp is None:
            return False
        return True

    def __hash__(self) -> int:
        base = hash((self.event_type, self.mft_reference, self.filename))
        if self.timestamp:
            base ^= hash(self.timestamp)
        return base

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ForensicEvent):
            return NotImplemented
        return (
            self.timestamp == other.timestamp
            and self.event_type == other.event_type
            and self.mft_reference == other.mft_reference
            and self.filename == other.filename
        )


@dataclass
class TimelineMetadata:
    source_counts: dict[str, int] = field(default_factory=dict)
    type_counts: dict[str, int] = field(default_factory=dict)
    time_range_start: datetime | None = None
    time_range_end: datetime | None = None
    total_events: int = 0
    correlated_events: int = 0
    unique_files: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_counts": self.source_counts,
            "type_counts": self.type_counts,
            "time_range_start": (
                self.time_range_start.isoformat() if self.time_range_start else None
            ),
            "time_range_end": (self.time_range_end.isoformat() if self.time_range_end else None),
            "total_events": self.total_events,
            "correlated_events": self.correlated_events,
            "unique_files": self.unique_files,
        }
