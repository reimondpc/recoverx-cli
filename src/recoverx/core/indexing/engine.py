from __future__ import annotations

import json
import logging
from typing import Any

from recoverx.core.artifacts.models import Artifact, FileArtifact
from recoverx.core.forensics.models import ForensicEvent

from .cache import HitTrackingCache
from .models import IndexConfig, IndexStats
from .schema import SchemaManager
from .storage import StorageBackend
from .transactions import TransactionManager

logger = logging.getLogger("recoverx")


class IndexEngine:
    def __init__(self, config: IndexConfig | None = None) -> None:
        self._config = config or IndexConfig()
        self._storage = StorageBackend(
            self._config.db_path,
            read_only=self._config.read_only,
            wal_mode=self._config.wal_mode,
        )
        self._transactions = TransactionManager(self._storage)
        self._cache = HitTrackingCache(max_size=self._config.cache_size)
        self._schema: SchemaManager | None = None
        self._opened = False

    def open(self) -> None:
        if self._opened:
            return
        self._storage.open()
        self._schema = SchemaManager(self._storage.conn)
        if not self._config.read_only:
            self._schema.ensure_schema()
        self._opened = True

    def close(self) -> None:
        if self._opened:
            self._storage.close()
            self._opened = False

    def __enter__(self) -> IndexEngine:
        self.open()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @property
    def storage(self) -> StorageBackend:
        return self._storage

    @property
    def cache(self) -> HitTrackingCache:
        return self._cache

    @property
    def config(self) -> IndexConfig:
        return self._config

    @property
    def is_read_only(self) -> bool:
        return self._config.read_only

    # ── Indexing ──────────────────────────────────────────────────

    def index_event(self, event: ForensicEvent, case_id: str = "") -> None:
        self._transactions.bulk_insert_events([self._event_to_dict(event, case_id)])

    def index_events(self, events: list[ForensicEvent], case_id: str = "") -> int:
        dicts = [self._event_to_dict(e, case_id) for e in events]
        return self._transactions.bulk_insert_events(dicts, self._config.batch_size)

    def index_artifact(self, artifact: Artifact, case_id: str = "") -> None:
        data = artifact.to_dict()
        data["case_id"] = case_id
        self._storage.execute(
            """
            INSERT OR IGNORE INTO artifacts
                (artifact_id, artifact_type, source, confidence, filename,
                 file_size, mft_reference, sha256, is_deleted, metadata,
                 evidence_chain, case_id, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                data.get("artifact_id", ""),
                type(artifact).__name__,
                data.get("source", ""),
                data.get("confidence", 0.8),
                data.get("filename", ""),
                data.get("file_size", 0),
                data.get("mft_reference", 0),
                data.get("sha256", ""),
                1 if data.get("is_deleted") else 0,
                json.dumps(data.get("metadata", {})),
                json.dumps(data.get("evidence_chain", [])),
                case_id,
                data.get("session_id", ""),
            ),
        )
        self._storage.commit()

    def index_file_artifact(self, artifact: FileArtifact, case_id: str = "") -> None:
        self.index_artifact(artifact, case_id)
        self._transactions.bulk_insert_files([artifact.to_dict()], self._config.batch_size)

    def index_hash(
        self, sha256_hash: str, filename: str = "", mft_ref: int = 0, case_id: str = ""
    ) -> None:
        row = self._storage.fetchone("SELECT id FROM hashes WHERE sha256 = ?", (sha256_hash,))
        if row:
            self._transactions.update_hash_duplicates(sha256_hash, filename, mft_ref)
        else:
            self._transactions.bulk_insert_hashes(
                [
                    {
                        "sha256": sha256_hash,
                        "duplicate_count": 1,
                        "total_size": 0,
                        "filenames": filename,
                        "mft_references": str(mft_ref),
                        "case_id": case_id,
                    }
                ]
            )

    def index_timeline(self, name: str, events: list[ForensicEvent], case_id: str = "") -> None:
        self.index_events(events, case_id)
        timestamps = [e.timestamp for e in events if e.timestamp]
        self._storage.execute(
            """
            INSERT INTO timelines
                (name, source, event_count, time_range_start, time_range_end, case_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                name,
                "multi",
                len(events),
                min(timestamps).isoformat() if timestamps else None,
                max(timestamps).isoformat() if timestamps else None,
                case_id,
            ),
        )
        self._storage.commit()

    def index_correlation(
        self,
        corr_type: str,
        source_a: str,
        id_a: int,
        source_b: str,
        id_b: int,
        confidence: float = 0.8,
        notes: str = "",
        case_id: str = "",
    ) -> None:
        self._transactions.bulk_insert_correlations(
            [
                {
                    "correlation_type": corr_type,
                    "source_a_type": source_a,
                    "source_a_id": id_a,
                    "source_b_type": source_b,
                    "source_b_id": id_b,
                    "confidence": confidence,
                    "notes": notes,
                    "case_id": case_id,
                }
            ]
        )

    # ── Querying ──────────────────────────────────────────────────

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
        return self._storage.search_events(
            event_type=event_type,
            source=source,
            filename=filename,
            since=since,
            until=until,
            mft_ref=mft_ref,
            deleted_only=deleted_only,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )

    def search_files(
        self,
        filename: str | None = None,
        sha256: str | None = None,
        mft_ref: int | None = None,
        deleted_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return self._storage.search_files(
            filename=filename,
            sha256=sha256,
            mft_ref=mft_ref,
            deleted_only=deleted_only,
            limit=limit,
            offset=offset,
        )

    def get_duplicates(self, sha256_hash: str) -> dict[str, Any] | None:
        row = self._storage.fetchone("SELECT * FROM hashes WHERE sha256 = ?", (sha256_hash,))
        return dict(row) if row else None

    def get_event_count(self) -> int:
        return self._storage.count_events()

    def get_file_count(self) -> int:
        return self._storage.count_files()

    # ── Stats & Maintenance ───────────────────────────────────────

    def stats(self) -> IndexStats:
        assert self._schema is not None, "IndexEngine not opened"
        st = self._schema.table_stats()
        sz = self._storage.size_bytes()
        return IndexStats(
            total_events=st.get("events", 0),
            total_artifacts=st.get("artifacts", 0),
            total_files=st.get("files", 0),
            total_hashes=st.get("hashes", 0),
            total_correlations=st.get("correlations", 0),
            unique_hashes=st.get("hashes", 0),
            db_size_bytes=sz,
            schema_version=1,
            indexed_sources=list(self._discover_sources()),
        )

    def integrity_check(self) -> dict[str, object]:
        assert self._schema is not None, "IndexEngine not opened"
        return self._schema.check_integrity()

    def vacuum(self) -> None:
        self._storage.vacuum()

    def analyze(self) -> None:
        self._storage.analyze()

    # ── Helpers ───────────────────────────────────────────────────

    def _event_to_dict(self, event: ForensicEvent, case_id: str = "") -> dict[str, Any]:
        return {
            "event_type": (
                event.event_type.value
                if hasattr(event.event_type, "value")
                else str(event.event_type)
            ),
            "source": event.source.value if hasattr(event.source, "value") else str(event.source),
            "timestamp": event.timestamp.isoformat() if event.timestamp else None,
            "filename": event.filename,
            "parent_name": event.parent_name,
            "mft_reference": event.mft_reference,
            "parent_mft_reference": event.parent_mft_reference,
            "previous_filename": event.previous_filename,
            "file_size": event.file_size,
            "confidence": event.confidence,
            "lsn": event.lsn,
            "usn_reason_flags": ",".join(event.usn_reason_flags),
            "notes": "; ".join(event.notes),
            "source_record": json.dumps(event.source_record),
            "case_id": case_id,
            "session_id": "",
        }

    def _discover_sources(self) -> set[str]:
        sources: set[str] = set()
        rows = self._storage.fetchall("SELECT DISTINCT source FROM events WHERE source != ''")
        for r in rows:
            sources.add(r["source"])
        return sources
