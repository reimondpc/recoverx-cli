from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Any


class BoundedCache:
    def __init__(self, max_size: int = 10000) -> None:
        self._max_size = max_size
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._lock = threading.RLock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            return None

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._cache[key] = value
            self._cache.move_to_end(key)
            self._evict()

    def set_many(self, items: dict[str, Any]) -> None:
        with self._lock:
            self._cache.update(items)
            for key in items:
                self._cache.move_to_end(key)
            self._evict()

    def delete(self, key: str) -> None:
        with self._lock:
            self._cache.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def _evict(self) -> None:
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._cache)

    @property
    def max_size(self) -> int:
        return self._max_size

    def hit_rate(self) -> float:
        return 0.0


class HitTrackingCache(BoundedCache):
    def __init__(self, max_size: int = 10000) -> None:
        super().__init__(max_size)
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        result = super().get(key)
        if result is not None:
            self._hits += 1
        else:
            self._misses += 1
        return result

    def hit_rate(self) -> float:
        total = self._hits + self._misses
        if total == 0:
            return 0.0
        return self._hits / total

    def stats(self) -> dict[str, int | float]:
        return {
            "hits": self._hits,
            "misses": self._misses,
            "size": self.size,
            "max_size": self._max_size,
            "hit_rate": round(self.hit_rate(), 4),
        }
