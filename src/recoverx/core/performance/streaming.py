from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("recoverx")


class StreamingIndexer:
    def __init__(self, batch_size: int = 1000, max_memory_mb: float = 256.0) -> None:
        self._batch_size = batch_size
        self._max_memory = max_memory_mb
        self._processed = 0
        self._batch: list[dict[str, Any]] = []

    def add(self, item: dict[str, Any]) -> int | None:
        self._batch.append(item)
        if len(self._batch) >= self._batch_size:
            return self.flush()
        return None

    def flush(self) -> int:
        count = len(self._batch)
        self._processed += count
        self._batch.clear()
        return count

    @property
    def processed(self) -> int:
        return self._processed

    @property
    def batch_size(self) -> int:
        return self._batch_size

    @property
    def buffered(self) -> int:
        return len(self._batch)
