from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("recoverx")


class TransactionManager:
    def __init__(self, storage: Any) -> None:
        self._storage = storage

    def bulk_insert_events(self, events: list[dict[str, Any]], batch_size: int = 1000) -> int:
        sql = """
            INSERT INTO events
                (event_type, source, timestamp, filename, parent_name,
                 mft_reference, parent_mft_reference, previous_filename,
                 file_size, confidence, lsn, usn_reason_flags, notes,
                 source_record, case_id, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        count = 0
        batch: list[tuple] = []
        for ev in events:
            batch.append(
                (
                    ev.get("event_type", ""),
                    ev.get("source", ""),
                    ev.get("timestamp"),
                    ev.get("filename", ""),
                    ev.get("parent_name", ""),
                    ev.get("mft_reference", 0),
                    ev.get("parent_mft_reference", 0),
                    ev.get("previous_filename", ""),
                    ev.get("file_size", 0),
                    ev.get("confidence", 0.8),
                    ev.get("lsn", 0),
                    ev.get("usn_reason_flags", ""),
                    ev.get("notes", ""),
                    ev.get("source_record", ""),
                    ev.get("case_id", ""),
                    ev.get("session_id", ""),
                )
            )
            count += 1
            if len(batch) >= batch_size:
                self._storage.executemany(sql, batch)
                batch = []
        if batch:
            self._storage.executemany(sql, batch)
        self._storage.commit()
        logger.debug("Bulk inserted %d events", count)
        return count

    def bulk_insert_files(self, files: list[dict[str, Any]], batch_size: int = 1000) -> int:
        sql = """
            INSERT OR IGNORE INTO files
                (filename, file_path, file_size, mft_reference,
                 parent_mft_reference, is_deleted, sha256,
                 created, modified, accessed, mft_modified,
                 case_id, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        count = 0
        batch: list[tuple] = []
        for f in files:
            ts = f.get("timestamps", {}) if isinstance(f.get("timestamps"), dict) else {}
            batch.append(
                (
                    f.get("filename", ""),
                    f.get("file_path", ""),
                    f.get("file_size", 0),
                    f.get("mft_reference", 0),
                    f.get("parent_mft_reference", 0),
                    1 if f.get("is_deleted") else 0,
                    f.get("sha256", ""),
                    ts.get("created"),
                    ts.get("modified"),
                    ts.get("accessed"),
                    ts.get("mft_modified"),
                    f.get("case_id", ""),
                    f.get("session_id", ""),
                )
            )
            count += 1
            if len(batch) >= batch_size:
                self._storage.executemany(sql, batch)
                batch = []
        if batch:
            self._storage.executemany(sql, batch)
        self._storage.commit()
        return count

    def bulk_insert_hashes(self, hashes: list[dict[str, Any]], batch_size: int = 1000) -> int:
        sql = """
            INSERT OR IGNORE INTO hashes
                (sha256, duplicate_count, total_size, filenames, mft_references, case_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        count = 0
        batch: list[tuple] = []
        for h in hashes:
            batch.append(
                (
                    h.get("sha256", ""),
                    h.get("duplicate_count", 1),
                    h.get("total_size", 0),
                    h.get("filenames", ""),
                    h.get("mft_references", ""),
                    h.get("case_id", ""),
                )
            )
            count += 1
            if len(batch) >= batch_size:
                self._storage.executemany(sql, batch)
                batch = []
        if batch:
            self._storage.executemany(sql, batch)
        self._storage.commit()
        return count

    def bulk_insert_correlations(
        self, correlations: list[dict[str, Any]], batch_size: int = 1000
    ) -> int:
        sql = """
            INSERT INTO correlations
                (correlation_type, source_a_type, source_a_id,
                 source_b_type, source_b_id, confidence, notes, case_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        count = 0
        batch: list[tuple] = []
        for c in correlations:
            batch.append(
                (
                    c.get("correlation_type", ""),
                    c.get("source_a_type", ""),
                    c.get("source_a_id", 0),
                    c.get("source_b_type", ""),
                    c.get("source_b_id", 0),
                    c.get("confidence", 0.8),
                    c.get("notes", ""),
                    c.get("case_id", ""),
                )
            )
            count += 1
            if len(batch) >= batch_size:
                self._storage.executemany(sql, batch)
                batch = []
        if batch:
            self._storage.executemany(sql, batch)
        self._storage.commit()
        return count

    def update_hash_duplicates(self, sha256: str, filename: str, mft_ref: int) -> None:
        self._storage.execute(
            """
            UPDATE hashes SET
                duplicate_count = duplicate_count + 1,
                last_seen = datetime('now'),
                filenames = CASE
                    WHEN filenames = '' THEN ?
                    ELSE filenames || ', ' || ?
                END,
                mft_references = CASE
                    WHEN mft_references = '' THEN ?
                    ELSE mft_references || ', ' || ?
                END
            WHERE sha256 = ?
        """,
            (filename, filename, str(mft_ref), str(mft_ref), sha256),
        )
        self._storage.commit()
