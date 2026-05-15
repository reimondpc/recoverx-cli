from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class USNRecord:
    record_length: int = 0
    major_version: int = 0
    minor_version: int = 0
    file_reference: int = 0
    parent_reference: int = 0
    usn: int = 0
    timestamp: datetime | None = None
    reason_flags: int = 0
    reason_names: list[str] = field(default_factory=list)
    source_info: int = 0
    security_id: int = 0
    file_attributes: int = 0
    file_name: str = ""
    raw_offset: int = 0
    raw_data: bytes = b""
    valid: bool = True
    validation_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_length": self.record_length,
            "major_version": self.major_version,
            "minor_version": self.minor_version,
            "file_reference": self.file_reference,
            "parent_reference": self.parent_reference,
            "usn": self.usn,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "reason_flags": hex(self.reason_flags),
            "reason_names": self.reason_names,
            "source_info": self.source_info,
            "security_id": self.security_id,
            "file_attributes": hex(self.file_attributes),
            "file_name": self.file_name,
            "raw_offset": self.raw_offset,
            "valid": self.valid,
        }


@dataclass
class USNJournalInfo:
    max_usn: int = 0
    allocation_delta: int = 0
    usn_page_size: int = 0
    record_count: int = 0
    major_version: int = 0
    minor_version: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_usn": self.max_usn,
            "allocation_delta": self.allocation_delta,
            "usn_page_size": self.usn_page_size,
            "record_count": self.record_count,
            "major_version": self.major_version,
            "minor_version": self.minor_version,
        }
