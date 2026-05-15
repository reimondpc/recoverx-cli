from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class BundleManifest:
    bundle_id: str
    created_at: str
    version: str = "1.0"
    total_events: int = 0
    total_findings: int = 0
    total_artifacts: int = 0
    investigator: str = ""
    case_id: str = ""
    notes: str = ""
    integrity_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "created_at": self.created_at,
            "version": self.version,
            "total_events": self.total_events,
            "total_findings": self.total_findings,
            "total_artifacts": self.total_artifacts,
            "investigator": self.investigator,
            "case_id": self.case_id,
            "notes": self.notes,
            "integrity_hash": self.integrity_hash,
        }


class ForensicBundle:
    def __init__(self, investigator: str = "", case_id: str = "") -> None:
        self._bundle_id = uuid.uuid4().hex[:16]
        self._manifest = BundleManifest(
            bundle_id=self._bundle_id,
            created_at=datetime.now().isoformat(),
            investigator=investigator,
            case_id=case_id,
        )
        self._events: list[dict[str, Any]] = []
        self._findings: list[dict[str, Any]] = []
        self._artifacts: list[dict[str, Any]] = []

    @property
    def manifest(self) -> BundleManifest:
        return self._manifest

    @property
    def bundle_id(self) -> str:
        return self._bundle_id

    def add_events(self, events: list[dict[str, Any]]) -> None:
        self._events.extend(events)
        self._manifest.total_events = len(self._events)

    def add_findings(self, findings: list[dict[str, Any]]) -> None:
        self._findings.extend(findings)
        self._manifest.total_findings = len(self._findings)

    def add_artifacts(self, artifacts: list[dict[str, Any]]) -> None:
        self._artifacts.extend(artifacts)
        self._manifest.total_artifacts = len(self._artifacts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest": self._manifest.to_dict(),
            "events": self._events,
            "findings": self._findings,
            "artifacts": self._artifacts,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def export(self, path: str) -> str:
        with open(path, "w") as f:
            f.write(self.to_json())
        return path
