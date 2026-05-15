from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class IndexConfig:
    db_path: str = "recoverx_forensic.db"
    batch_size: int = 1000
    cache_size: int = 10000
    read_only: bool = False
    wal_mode: bool = True
    auto_vacuum: bool = True
    log_queries: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "db_path": self.db_path,
            "batch_size": self.batch_size,
            "cache_size": self.cache_size,
            "read_only": self.read_only,
            "wal_mode": self.wal_mode,
            "auto_vacuum": self.auto_vacuum,
            "log_queries": self.log_queries,
        }


@dataclass
class IndexStats:
    total_events: int = 0
    total_artifacts: int = 0
    total_files: int = 0
    total_hashes: int = 0
    unique_hashes: int = 0
    total_correlations: int = 0
    db_size_bytes: int = 0
    schema_version: int = 0
    indexed_sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_events": self.total_events,
            "total_artifacts": self.total_artifacts,
            "total_files": self.total_files,
            "total_hashes": self.total_hashes,
            "unique_hashes": self.unique_hashes,
            "total_correlations": self.total_correlations,
            "db_size_bytes": self.db_size_bytes,
            "schema_version": self.schema_version,
            "indexed_sources": self.indexed_sources,
        }
