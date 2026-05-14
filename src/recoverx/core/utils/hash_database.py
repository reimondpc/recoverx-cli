from __future__ import annotations

import json
import logging
from pathlib import Path

from recoverx.core.utils.hashing import sha256, sha256_file

logger = logging.getLogger("recoverx")


class HashDatabase:
    def __init__(self, db_path: str = "recovered/.hashdb.json") -> None:
        self.db_path = Path(db_path)
        self._hashes: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self.db_path.exists():
            try:
                data = json.loads(self.db_path.read_text())
                self._hashes = data.get("hashes", {})
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load hash database: %s", e)
                self._hashes = {}

    def _save(self) -> None:
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "version": 1,
                "total_entries": len(self._hashes),
                "hashes": self._hashes,
            }
            self.db_path.write_text(json.dumps(data, indent=2))
        except OSError as e:
            logger.warning("Failed to save hash database: %s", e)

    def add(self, digest: str, file_path: str, file_size: int, file_type: str) -> None:
        if digest not in self._hashes:
            self._hashes[digest] = {
                "first_seen_path": file_path,
                "size": file_size,
                "type": file_type,
                "count": 1,
            }
        else:
            self._hashes[digest]["count"] += 1
        self._save()

    def known(self, digest: str) -> bool:
        return digest in self._hashes

    def is_duplicate(self, data: bytes) -> bool:
        return self.known(sha256(data))

    def is_duplicate_file(self, path: str) -> bool:
        return self.known(sha256_file(path))

    @property
    def total_unique(self) -> int:
        return len(self._hashes)

    @property
    def total_occurrences(self) -> int:
        return sum(e["count"] for e in self._hashes.values())

    @property
    def total_size(self) -> int:
        return sum(e["size"] * e["count"] for e in self._hashes.values())

    def statistics(self) -> dict:
        return {
            "unique_files": self.total_unique,
            "total_occurrences": self.total_occurrences,
            "total_size_bytes": self.total_size,
            "file_types": self._type_counts(),
        }

    def _type_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for entry in self._hashes.values():
            ft = entry["type"]
            counts[ft] = counts.get(ft, 0) + 1
        return counts

    def clear(self) -> None:
        self._hashes.clear()
        if self.db_path.exists():
            self.db_path.unlink()
