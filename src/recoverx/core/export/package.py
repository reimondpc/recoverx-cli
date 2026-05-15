from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class PackageMetadata:
    package_id: str
    created_at: str
    version: str = "1.0"
    case_id: str = ""
    investigator: str = ""
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "package_id": self.package_id,
            "created_at": self.created_at,
            "version": self.version,
            "case_id": self.case_id,
            "investigator": self.investigator,
            "description": self.description,
        }


class SQLitePackage:
    def __init__(self, path: str, investigator: str = "", case_id: str = "") -> None:
        self._path = path
        self._metadata = PackageMetadata(
            package_id=uuid.uuid4().hex[:16],
            created_at=datetime.now().isoformat(),
            investigator=investigator,
            case_id=case_id,
        )

    def create(self) -> None:
        path = Path(self._path)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS package_metadata (
                key TEXT PRIMARY KEY, value TEXT
            )
        """)
        conn.execute(
            "INSERT INTO package_metadata (key, value) VALUES (?, ?)",
            ("package_id", self._metadata.package_id),
        )
        conn.execute(
            "INSERT INTO package_metadata (key, value) VALUES (?, ?)",
            ("created_at", self._metadata.created_at),
        )
        conn.execute(
            "INSERT INTO package_metadata (key, value) VALUES (?, ?)",
            ("version", self._metadata.version),
        )
        conn.execute("""
            CREATE TABLE IF NOT EXISTS export_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT, source TEXT, timestamp TEXT,
                filename TEXT, mft_reference INTEGER, confidence REAL,
                notes TEXT, case_id TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS export_findings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                finding_id TEXT UNIQUE, category TEXT, severity TEXT,
                confidence REAL, title TEXT, description TEXT,
                mft_references TEXT, case_id TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS export_artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                artifact_id TEXT UNIQUE, artifact_type TEXT, source TEXT,
                filename TEXT, sha256 TEXT, confidence REAL, case_id TEXT
            )
        """)
        conn.commit()
        conn.close()

    def write_events(self, events: list[dict[str, Any]]) -> int:
        conn = sqlite3.connect(self._path)
        count = 0
        for ev in events:
            conn.execute(
                """INSERT INTO export_events
                   (event_type, source, timestamp, filename, mft_reference,
                    confidence, notes, case_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ev.get("event_type", ""),
                    ev.get("source", ""),
                    ev.get("timestamp"),
                    ev.get("filename", ""),
                    ev.get("mft_reference", 0),
                    ev.get("confidence", 0.0),
                    ev.get("notes", ""),
                    ev.get("case_id", ""),
                ),
            )
            count += 1
        conn.commit()
        conn.close()
        return count

    def write_findings(self, findings: list[dict[str, Any]]) -> int:
        conn = sqlite3.connect(self._path)
        count = 0
        for f in findings:
            cursor = conn.execute(
                """INSERT OR IGNORE INTO export_findings
                   (finding_id, category, severity, confidence, title,
                    description, mft_references, case_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    f.get("id", ""),
                    f.get("category", ""),
                    f.get("severity", ""),
                    f.get("confidence", 0.0),
                    f.get("title", ""),
                    f.get("description", ""),
                    json.dumps(f.get("mft_references", [])),
                    f.get("case_id", ""),
                ),
            )
            count += cursor.rowcount
        conn.commit()
        conn.close()
        return count

    @property
    def path(self) -> str:
        return self._path

    @property
    def metadata(self) -> PackageMetadata:
        return self._metadata
