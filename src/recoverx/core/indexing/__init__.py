"""Forensic indexing engine for persistent storage and retrieval.

Provides SQLite-backed indexing of forensic events, artifacts,
file metadata, timestamps, and hashes for fast querying and
correlation across large datasets.
"""

from __future__ import annotations

from .engine import IndexEngine
from .models import IndexConfig, IndexStats
from .schema import SchemaManager
from .storage import StorageBackend

__all__ = [
    "IndexEngine",
    "IndexConfig",
    "IndexStats",
    "SchemaManager",
    "StorageBackend",
]
