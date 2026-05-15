from __future__ import annotations

import sqlite3

FORENSIC_SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    source TEXT NOT NULL,
    timestamp TEXT,
    filename TEXT NOT NULL DEFAULT '',
    parent_name TEXT DEFAULT '',
    mft_reference INTEGER DEFAULT 0,
    parent_mft_reference INTEGER DEFAULT 0,
    previous_filename TEXT DEFAULT '',
    file_size INTEGER DEFAULT 0,
    confidence REAL DEFAULT 0.8,
    lsn INTEGER DEFAULT 0,
    usn_reason_flags TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    source_record TEXT DEFAULT '',
    case_id TEXT DEFAULT '',
    session_id TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_source ON events(source);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_filename ON events(filename);
CREATE INDEX IF NOT EXISTS idx_events_mft ON events(mft_reference);
CREATE INDEX IF NOT EXISTS idx_events_case ON events(case_id);
CREATE INDEX IF NOT EXISTS idx_events_parent_mft ON events(parent_mft_reference);
CREATE INDEX IF NOT EXISTS idx_events_confidence ON events(confidence);

CREATE TABLE IF NOT EXISTS artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artifact_id TEXT UNIQUE NOT NULL,
    artifact_type TEXT NOT NULL,
    source TEXT DEFAULT '',
    confidence REAL DEFAULT 0.8,
    filename TEXT DEFAULT '',
    file_size INTEGER DEFAULT 0,
    mft_reference INTEGER DEFAULT 0,
    sha256 TEXT DEFAULT '',
    is_deleted INTEGER DEFAULT 0,
    metadata TEXT DEFAULT '{}',
    evidence_chain TEXT DEFAULT '',
    case_id TEXT DEFAULT '',
    session_id TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_artifacts_type ON artifacts(artifact_type);
CREATE INDEX IF NOT EXISTS idx_artifacts_sha ON artifacts(sha256);
CREATE INDEX IF NOT EXISTS idx_artifacts_mft ON artifacts(mft_reference);
CREATE INDEX IF NOT EXISTS idx_artifacts_deleted ON artifacts(is_deleted);
CREATE INDEX IF NOT EXISTS idx_artifacts_case ON artifacts(case_id);

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    file_path TEXT DEFAULT '',
    file_size INTEGER DEFAULT 0,
    mft_reference INTEGER DEFAULT 0,
    parent_mft_reference INTEGER DEFAULT 0,
    is_deleted INTEGER DEFAULT 0,
    sha256 TEXT DEFAULT '',
    created TEXT,
    modified TEXT,
    accessed TEXT,
    mft_modified TEXT,
    case_id TEXT DEFAULT '',
    session_id TEXT DEFAULT '',
    first_seen TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_files_name ON files(filename);
CREATE INDEX IF NOT EXISTS idx_files_sha ON files(sha256);
CREATE INDEX IF NOT EXISTS idx_files_mft ON files(mft_reference);
CREATE INDEX IF NOT EXISTS idx_files_deleted ON files(is_deleted);
CREATE INDEX IF NOT EXISTS idx_files_case ON files(case_id);

CREATE TABLE IF NOT EXISTS hashes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sha256 TEXT UNIQUE NOT NULL,
    duplicate_count INTEGER DEFAULT 1,
    total_size INTEGER DEFAULT 0,
    first_seen TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen TEXT NOT NULL DEFAULT (datetime('now')),
    filenames TEXT DEFAULT '',
    mft_references TEXT DEFAULT '',
    case_id TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_hashes_sha ON hashes(sha256);
CREATE INDEX IF NOT EXISTS idx_hashes_count ON hashes(duplicate_count);
CREATE INDEX IF NOT EXISTS idx_hashes_case ON hashes(case_id);

CREATE TABLE IF NOT EXISTS timelines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    source TEXT DEFAULT '',
    event_count INTEGER DEFAULT 0,
    time_range_start TEXT,
    time_range_end TEXT,
    case_id TEXT DEFAULT '',
    session_id TEXT DEFAULT '',
    config TEXT DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_timelines_case ON timelines(case_id);
CREATE INDEX IF NOT EXISTS idx_timelines_name ON timelines(name);

CREATE TABLE IF NOT EXISTS correlations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    correlation_type TEXT NOT NULL,
    source_a_type TEXT NOT NULL,
    source_a_id INTEGER DEFAULT 0,
    source_b_type TEXT NOT NULL,
    source_b_id INTEGER DEFAULT 0,
    confidence REAL DEFAULT 0.8,
    notes TEXT DEFAULT '',
    case_id TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_corr_type ON correlations(correlation_type);
CREATE INDEX IF NOT EXISTS idx_corr_a ON correlations(source_a_type, source_a_id);
CREATE INDEX IF NOT EXISTS idx_corr_b ON correlations(source_b_type, source_b_id);
CREATE INDEX IF NOT EXISTS idx_corr_case ON correlations(case_id);
"""


class SchemaManager:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def ensure_schema(self) -> int:
        cursor = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        )
        if not cursor.fetchone():
            self._conn.executescript(SCHEMA_SQL)
            self._conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)", (FORENSIC_SCHEMA_VERSION,)
            )
            self._conn.commit()
            return FORENSIC_SCHEMA_VERSION

        row = self._conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        current_version = row[0] if row and row[0] else 0

        if current_version < FORENSIC_SCHEMA_VERSION:
            self._run_migrations(current_version)
            self._conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)", (FORENSIC_SCHEMA_VERSION,)
            )
            self._conn.commit()

        return FORENSIC_SCHEMA_VERSION

    def _run_migrations(self, from_version: int) -> None:
        if from_version < 1:
            self._conn.executescript(SCHEMA_SQL)

    def check_integrity(self) -> dict[str, object]:
        row = self._conn.execute("PRAGMA integrity_check").fetchone()
        ok = row and row[0] == "ok"
        page_count = self._conn.execute("PRAGMA page_count").fetchone()
        page_size = self._conn.execute("PRAGMA page_size").fetchone()
        return {
            "integrity_check": "ok" if ok else (row[0] if row else "unknown"),
            "page_count": page_count[0] if page_count else 0,
            "page_size": page_size[0] if page_size else 0,
        }

    def table_stats(self) -> dict[str, int]:
        stats = {}
        for table in ["events", "artifacts", "files", "hashes", "timelines", "correlations"]:
            row = self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            stats[table] = row[0] if row else 0
        return stats
