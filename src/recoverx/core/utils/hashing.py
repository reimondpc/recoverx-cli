"""SHA-256 hashing utilities for forensic integrity verification."""

from __future__ import annotations

import hashlib


def sha256(data: bytes) -> str:
    """Compute the SHA-256 hex digest of *data*."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    """Compute the SHA-256 hex digest of a file at *path* (streaming)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


class HashManager:
    """Manages SHA-256 hashing for recovered files.

    Tracks all computed hashes to enable deduplication and integrity
    verification.
    """

    def __init__(self) -> None:
        self._hashes: dict[str, str] = {}

    def compute(self, data: bytes) -> str:
        digest = sha256(data)
        self._hashes[digest] = self._hashes.get(digest, digest)
        return digest

    def is_duplicate(self, digest: str) -> bool:
        return digest in self._hashes

    @property
    def unique_count(self) -> int:
        return len(self._hashes)

    def check_integrity(self, path: str, expected: str) -> bool:
        return sha256_file(path) == expected
