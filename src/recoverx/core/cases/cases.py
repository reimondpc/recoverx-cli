from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from recoverx.core.indexing.storage import StorageBackend

from .models import Bookmark, CaseMetadata, SavedQuery, TaggedArtifact


class Case:
    def __init__(self, metadata: CaseMetadata, storage: StorageBackend) -> None:
        self._metadata = metadata
        self._storage = storage

    @property
    def metadata(self) -> CaseMetadata:
        return self._metadata

    @property
    def case_id(self) -> str:
        return self._metadata.case_id

    # ── Bookmarks ─────────────────────────────────────────────

    def add_bookmark(
        self, event_id: int = 0, artifact_id: str = "", notes: str = "", label: str = ""
    ) -> Bookmark:
        bm = Bookmark(
            bookmark_id=uuid.uuid4().hex[:16],
            case_id=self.case_id,
            event_id=event_id,
            artifact_id=artifact_id,
            notes=notes,
            created_at=datetime.utcnow(),
            label=label,
        )
        self._storage.execute(
            """
            INSERT INTO case_bookmarks (bookmark_id, case_id, event_id, artifact_id, notes, label)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (bm.bookmark_id, bm.case_id, bm.event_id, bm.artifact_id, bm.notes, bm.label),
        )
        self._storage.commit()
        return bm

    def get_bookmarks(self) -> list[Bookmark]:
        rows = self._storage.fetchall(
            "SELECT * FROM case_bookmarks WHERE case_id = ? ORDER BY created_at DESC",
            (self.case_id,),
        )
        return [_row_to_bookmark(r) for r in rows]

    def remove_bookmark(self, bookmark_id: str) -> None:
        self._storage.execute("DELETE FROM case_bookmarks WHERE bookmark_id = ?", (bookmark_id,))
        self._storage.commit()

    # ── Saved Queries ─────────────────────────────────────────

    def save_query(self, name: str, query_string: str, description: str = "") -> SavedQuery:
        sq = SavedQuery(
            query_id=uuid.uuid4().hex[:16],
            name=name,
            query_string=query_string,
            case_id=self.case_id,
            created_at=datetime.utcnow(),
            description=description,
        )
        self._storage.execute(
            """
            INSERT INTO case_queries (query_id, name, query_string, case_id, description)
            VALUES (?, ?, ?, ?, ?)
        """,
            (sq.query_id, sq.name, sq.query_string, sq.case_id, sq.description),
        )
        self._storage.commit()
        return sq

    def get_saved_queries(self) -> list[SavedQuery]:
        rows = self._storage.fetchall(
            "SELECT * FROM case_queries WHERE case_id = ? ORDER BY created_at DESC", (self.case_id,)
        )
        return [_row_to_saved_query(r) for r in rows]

    def delete_query(self, query_id: str) -> None:
        self._storage.execute("DELETE FROM case_queries WHERE query_id = ?", (query_id,))
        self._storage.commit()

    # ── Tags ──────────────────────────────────────────────────

    def tag_artifact(self, artifact_id: str, tag: str, source: str = "") -> TaggedArtifact:
        ta = TaggedArtifact(
            tag=tag,
            artifact_id=artifact_id,
            case_id=self.case_id,
            source=source,
            created_at=datetime.utcnow(),
        )
        self._storage.execute(
            """
            INSERT OR IGNORE INTO case_tags (tag, artifact_id, case_id, source)
            VALUES (?, ?, ?, ?)
        """,
            (ta.tag, ta.artifact_id, ta.case_id, ta.source),
        )
        self._storage.commit()
        return ta

    def get_tagged_artifacts(self, tag: str | None = None) -> list[TaggedArtifact]:
        if tag:
            rows = self._storage.fetchall(
                "SELECT * FROM case_tags WHERE case_id = ? AND tag = ?", (self.case_id, tag)
            )
        else:
            rows = self._storage.fetchall(
                "SELECT * FROM case_tags WHERE case_id = ?", (self.case_id,)
            )
        return [_row_to_tagged(r) for r in rows]

    def remove_tag(self, artifact_id: str, tag: str) -> None:
        self._storage.execute(
            "DELETE FROM case_tags WHERE artifact_id = ? AND tag = ?", (artifact_id, tag)
        )
        self._storage.commit()

    # ── Notes ─────────────────────────────────────────────────

    def add_note(self, event_id: int, note: str) -> None:
        self._storage.execute(
            """
            INSERT INTO case_notes (case_id, event_id, note)
            VALUES (?, ?, ?)
        """,
            (self.case_id, event_id, note),
        )
        self._storage.commit()

    def get_notes(self, event_id: int | None = None) -> list[dict[str, Any]]:
        if event_id is not None:
            rows = self._storage.fetchall(
                "SELECT * FROM case_notes WHERE case_id = ? AND event_id = ? ORDER BY created_at",
                (self.case_id, event_id),
            )
        else:
            rows = self._storage.fetchall(
                "SELECT * FROM case_notes WHERE case_id = ? ORDER BY created_at", (self.case_id,)
            )
        return [dict(r) for r in rows]

    def to_dict(self) -> dict[str, Any]:
        return self._metadata.to_dict()


class CaseManager:
    def __init__(self, storage: StorageBackend) -> None:
        self._storage = storage
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        self._storage.execute("""
            CREATE TABLE IF NOT EXISTS case_metadata (
                case_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                examiner TEXT DEFAULT '',
                status TEXT DEFAULT 'open',
                tags TEXT DEFAULT '[]',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        self._storage.execute("""
            CREATE TABLE IF NOT EXISTS case_bookmarks (
                bookmark_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                event_id INTEGER DEFAULT 0,
                artifact_id TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                label TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        self._storage.execute("""
            CREATE TABLE IF NOT EXISTS case_queries (
                query_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                query_string TEXT NOT NULL,
                case_id TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        self._storage.execute("""
            CREATE TABLE IF NOT EXISTS case_tags (
                tag TEXT NOT NULL,
                artifact_id TEXT NOT NULL,
                case_id TEXT NOT NULL,
                source TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (tag, artifact_id, case_id)
            )
        """)
        self._storage.execute("""
            CREATE TABLE IF NOT EXISTS case_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT NOT NULL,
                event_id INTEGER DEFAULT 0,
                note TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        self._storage.commit()

    def create_case(self, name: str, description: str = "", examiner: str = "") -> Case:
        case_id = uuid.uuid4().hex[:16]
        meta = CaseMetadata(
            case_id=case_id,
            name=name,
            description=description,
            examiner=examiner,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            status="open",
        )
        self._storage.execute(
            """
            INSERT INTO case_metadata (case_id, name, description, examiner, status)
            VALUES (?, ?, ?, ?, ?)
        """,
            (case_id, name, description, examiner, "open"),
        )
        self._storage.commit()
        return Case(meta, self._storage)

    def get_case(self, case_id: str) -> Case | None:
        row = self._storage.fetchone("SELECT * FROM case_metadata WHERE case_id = ?", (case_id,))
        if not row:
            return None
        meta = CaseMetadata(
            case_id=row["case_id"],
            name=row["name"],
            description=row["description"],
            examiner=row["examiner"],
            status=row["status"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
        )
        return Case(meta, self._storage)

    def list_cases(self, status: str | None = None) -> list[CaseMetadata]:
        if status:
            rows = self._storage.fetchall(
                "SELECT * FROM case_metadata WHERE status = ? ORDER BY created_at DESC", (status,)
            )
        else:
            rows = self._storage.fetchall("SELECT * FROM case_metadata ORDER BY created_at DESC")
        return [_row_to_case_meta(r) for r in rows]

    def close_case(self, case_id: str) -> None:
        self._storage.execute(
            "UPDATE case_metadata SET status = 'closed',"
            " updated_at = datetime('now') WHERE case_id = ?",
            (case_id,),
        )
        self._storage.commit()

    def reopen_case(self, case_id: str) -> None:
        self._storage.execute(
            "UPDATE case_metadata SET status = 'open',"
            " updated_at = datetime('now') WHERE case_id = ?",
            (case_id,),
        )
        self._storage.commit()

    def delete_case(self, case_id: str) -> None:
        for table in ("case_metadata", "case_bookmarks", "case_queries", "case_tags", "case_notes"):
            self._storage.execute(f"DELETE FROM {table} WHERE case_id = ?", (case_id,))
        self._storage.commit()


def _row_to_case_meta(row: Any) -> CaseMetadata:
    tags_raw = row["tags"] if "tags" in row else "[]"
    return CaseMetadata(
        case_id=row["case_id"],
        name=row["name"],
        description=row["description"],
        examiner=row["examiner"],
        status=row["status"],
        tags=json.loads(tags_raw) if isinstance(tags_raw, str) else [],
    )


def _row_to_bookmark(row: Any) -> Bookmark:
    return Bookmark(
        bookmark_id=row["bookmark_id"],
        case_id=row["case_id"],
        event_id=row["event_id"],
        artifact_id=row["artifact_id"],
        notes=row["notes"],
        label=row["label"],
    )


def _row_to_saved_query(row: Any) -> SavedQuery:
    return SavedQuery(
        query_id=row["query_id"],
        name=row["name"],
        query_string=row["query_string"],
        case_id=row["case_id"],
        description=row["description"],
    )


def _row_to_tagged(row: Any) -> TaggedArtifact:
    return TaggedArtifact(
        tag=row["tag"],
        artifact_id=row["artifact_id"],
        case_id=row["case_id"],
        source=row["source"],
    )
