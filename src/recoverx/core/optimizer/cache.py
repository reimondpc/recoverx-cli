from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CachedResult:
    query: str
    result: list[dict[str, Any]]
    cached_at: float
    ttl_seconds: float
    hit_count: int = 0

    @property
    def is_expired(self) -> bool:
        return time.time() - self.cached_at > self.ttl_seconds


class QueryCache:
    def __init__(self, max_size: int = 1000, default_ttl: float = 60.0) -> None:
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._cache: dict[str, CachedResult] = {}
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, query: str) -> list[dict[str, Any]] | None:
        key = self._make_key(query)
        with self._lock:
            entry = self._cache.get(key)
            if entry and not entry.is_expired:
                entry.hit_count += 1
                self._hits += 1
                return entry.result
            if entry:
                del self._cache[key]
            self._misses += 1
            return None

    def set(self, query: str, result: list[dict[str, Any]], ttl: float | None = None) -> None:
        key = self._make_key(query)
        with self._lock:
            if len(self._cache) >= self._max_size:
                self._evict()
            self._cache[key] = CachedResult(
                query=query,
                result=result,
                cached_at=time.time(),
                ttl_seconds=ttl or self._default_ttl,
            )

    def invalidate(self, query: str) -> bool:
        key = self._make_key(query)
        with self._lock:
            return self._cache.pop(key, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def _make_key(self, query: str) -> str:
        normalized = " ".join(query.strip().lower().split())
        return hashlib.md5(normalized.encode()).hexdigest()

    def _evict(self) -> None:
        oldest = min(self._cache.keys(), key=lambda k: self._cache[k].cached_at)
        del self._cache[oldest]

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    @property
    def size(self) -> int:
        return len(self._cache)

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "size": self.size,
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self.hit_rate,
            "default_ttl": self._default_ttl,
        }
