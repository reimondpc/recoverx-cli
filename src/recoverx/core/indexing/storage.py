from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any, cast


class StorageBackend:
    def __init__(self, db_path: str, read_only: bool = False, wal_mode: bool = True) -> None:
        self._db_path = db_path
        self._read_only = read_only
        self._wal_mode = wal_mode
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self._open_count = 0

    def open(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._open_count += 1
                return

            path = Path(self._db_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            if self._read_only:
                self._conn = sqlite3.connect(f"file:{path.absolute()}?mode=ro", uri=True)
            else:
                self._conn = sqlite3.connect(str(path))

            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA cache_size=-65536")
            self._conn.execute("PRAGMA temp_store=MEMORY")
            self._conn.execute("PRAGMA mmap_size=268435456")
            self._conn.execute("PRAGMA foreign_keys=ON")

            self._conn.row_factory = sqlite3.Row
            self._open_count = 1

    def close(self) -> None:
        with self._lock:
            if self._conn is None:
                return
            self._open_count -= 1
            if self._open_count <= 0:
                try:
                    self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                except sqlite3.Error:
                    pass
                self._conn.close()
                self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("StorageBackend not opened")
        return self._conn

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self.conn.execute(sql, params)

    def execute_many(self, sql: str, seq: list[tuple]) -> None:
        self.conn.executemany(sql, seq)

    def executemany(self, sql: str, params_list: list[tuple]) -> None:
        self.conn.executemany(sql, params_list)

    def fetchone(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        cur = self.conn.execute(sql, params)
        return cast(sqlite3.Row | None, cur.fetchone())

    def fetchall(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, params).fetchall()

    def commit(self) -> None:
        self.conn.commit()

    def transaction(self) -> StorageTransaction:
        return StorageTransaction(self)

    @property
    def db_path(self) -> str:
        return self._db_path

    @property
    def is_read_only(self) -> bool:
        return self._read_only

    def vacuum(self) -> None:
        if not self._read_only:
            self.conn.execute("VACUUM")

    def analyze(self) -> None:
        if not self._read_only:
            self.conn.execute("ANALYZE")

    def size_bytes(self) -> int:
        path = Path(self._db_path)
        if path.exists():
            return path.stat().st_size
        wal = Path(str(self._db_path) + "-wal")
        shm = Path(str(self._db_path) + "-shm")
        total = path.stat().st_size
        if wal.exists():
            total += wal.stat().st_size
        if shm.exists():
            total += shm.stat().st_size
        return total

    def search_events(
        self,
        event_type: str | None = None,
        source: str | None = None,
        filename: str | None = None,
        since: str | None = None,
        until: str | None = None,
        mft_ref: int | None = None,
        deleted_only: bool = False,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "timestamp",
        sort_dir: str = "DESC",
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []

        if event_type:
            clauses.append("event_type = ?")
            params.append(event_type)
        if source:
            clauses.append("source = ?")
            params.append(source)
        if filename:
            clauses.append("filename LIKE ?")
            params.append(f"%{filename}%")
        if since:
            clauses.append("timestamp >= ?")
            params.append(since)
        if until:
            clauses.append("timestamp <= ?")
            params.append(until)
        if mft_ref is not None:
            clauses.append("(mft_reference = ? OR parent_mft_reference = ?)")
            params.extend([mft_ref, mft_ref])
        if deleted_only:
            clauses.append("event_type = 'FILE_DELETED'")

        where = " AND ".join(clauses) if clauses else "1=1"

        sort_col = (
            sort_by
            if sort_by
            in ("timestamp", "event_type", "source", "filename", "mft_reference", "confidence")
            else "timestamp"
        )
        sort_direction = sort_dir if sort_dir.upper() in ("ASC", "DESC") else "DESC"

        sql = (
            f"SELECT * FROM events WHERE {where}"
            f" ORDER BY {sort_col} {sort_direction} LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])

        rows = self.fetchall(sql, tuple(params))
        return [dict(r) for r in rows]

    def search_files(
        self,
        filename: str | None = None,
        sha256: str | None = None,
        mft_ref: int | None = None,
        deleted_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []

        if filename:
            clauses.append("filename LIKE ?")
            params.append(f"%{filename}%")
        if sha256:
            clauses.append("sha256 = ?")
            params.append(sha256)
        if mft_ref is not None:
            clauses.append("mft_reference = ?")
            params.append(mft_ref)
        if deleted_only:
            clauses.append("is_deleted = 1")

        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"SELECT * FROM files WHERE {where} ORDER BY first_seen DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self.fetchall(sql, tuple(params))
        return [dict(r) for r in rows]

    def count_events(self) -> int:
        row = self.fetchone("SELECT COUNT(*) AS cnt FROM events")
        return row["cnt"] if row else 0

    def count_files(self) -> int:
        row = self.fetchone("SELECT COUNT(*) AS cnt FROM files")
        return row["cnt"] if row else 0


class StorageTransaction:
    def __init__(self, backend: StorageBackend) -> None:
        self._backend = backend
        self._active = False

    def __enter__(self) -> StorageBackend:
        self._backend.conn.execute("BEGIN IMMEDIATE")
        self._active = True
        return self._backend

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self._active = False
        if exc_type is None:
            self._backend.conn.commit()
        else:
            self._backend.conn.rollback()
