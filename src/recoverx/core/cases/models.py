from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class CaseMetadata:
    case_id: str = ""
    name: str = ""
    description: str = ""
    examiner: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
    status: str = "open"
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "name": self.name,
            "description": self.description,
            "examiner": self.examiner,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "status": self.status,
            "tags": self.tags,
        }


@dataclass
class SavedQuery:
    query_id: str = ""
    name: str = ""
    query_string: str = ""
    case_id: str = ""
    created_at: datetime | None = None
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "name": self.name,
            "query_string": self.query_string,
            "case_id": self.case_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "description": self.description,
        }


@dataclass
class Bookmark:
    bookmark_id: str = ""
    case_id: str = ""
    event_id: int = 0
    artifact_id: str = ""
    notes: str = ""
    created_at: datetime | None = None
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "bookmark_id": self.bookmark_id,
            "case_id": self.case_id,
            "event_id": self.event_id,
            "artifact_id": self.artifact_id,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "label": self.label,
        }


@dataclass
class TaggedArtifact:
    tag: str = ""
    artifact_id: str = ""
    case_id: str = ""
    source: str = ""
    created_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tag": self.tag,
            "artifact_id": self.artifact_id,
            "case_id": self.case_id,
            "source": self.source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
