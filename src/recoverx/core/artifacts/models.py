from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Artifact:
    artifact_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    source: str = ""
    confidence: float = 0.8
    metadata: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    evidence_chain: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "source": self.source,
            "confidence": round(self.confidence, 2),
            "metadata": self.metadata,
            "notes": self.notes,
            "evidence_chain": self.evidence_chain,
        }


@dataclass
class FileArtifact(Artifact):
    filename: str = ""
    file_path: str = ""
    file_size: int = 0
    mft_reference: int = 0
    parent_mft_reference: int = 0
    is_deleted: bool = False
    sha256: str = ""
    timestamps: dict[str, datetime | None] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        ts = {}
        for k, v in self.timestamps.items():
            ts[k] = v.isoformat() if v else None
        base.update(
            {
                "filename": self.filename,
                "file_path": self.file_path,
                "file_size": self.file_size,
                "mft_reference": self.mft_reference,
                "parent_mft_reference": self.parent_mft_reference,
                "is_deleted": self.is_deleted,
                "sha256": self.sha256,
                "timestamps": ts,
            }
        )
        return base


@dataclass
class TimelineArtifact(Artifact):
    event_type: str = ""
    timestamp: datetime | None = None
    filename: str = ""
    previous_filename: str = ""
    mft_reference: int = 0
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            {
                "event_type": self.event_type,
                "timestamp": self.timestamp.isoformat() if self.timestamp else None,
                "filename": self.filename,
                "previous_filename": self.previous_filename,
                "mft_reference": self.mft_reference,
                "source": self.source,
            }
        )
        return base


@dataclass
class JournalArtifact(Artifact):
    journal_type: str = ""
    record_count: int = 0
    reason_flags: list[str] = field(default_factory=list)
    lsn_range: tuple[int, int] = (0, 0)
    mft_references: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            {
                "journal_type": self.journal_type,
                "record_count": self.record_count,
                "reason_flags": self.reason_flags,
                "lsn_range": list(self.lsn_range),
                "mft_references": self.mft_references[:20],
            }
        )
        return base


@dataclass
class DeletedArtifact(Artifact):
    filename: str = ""
    original_path: str = ""
    mft_reference: int = 0
    deletion_time: datetime | None = None
    recovery_potential: str = "unknown"
    file_size: int = 0

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            {
                "filename": self.filename,
                "original_path": self.original_path,
                "mft_reference": self.mft_reference,
                "deletion_time": self.deletion_time.isoformat() if self.deletion_time else None,
                "recovery_potential": self.recovery_potential,
                "file_size": self.file_size,
            }
        )
        return base


@dataclass
class HashArtifact(Artifact):
    sha256: str = ""
    known_duplicates: int = 1
    file_references: list[int] = field(default_factory=list)
    first_seen: datetime | None = None
    filename: str = ""

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            {
                "sha256": self.sha256,
                "known_duplicates": self.known_duplicates,
                "file_references": self.file_references,
                "first_seen": self.first_seen.isoformat() if self.first_seen else None,
                "filename": self.filename,
            }
        )
        return base
