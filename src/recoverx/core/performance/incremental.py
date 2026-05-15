from __future__ import annotations

from typing import Any


class IncrementalIndexer:
    def __init__(self) -> None:
        self._last_position: int = 0
        self._indexed_count: int = 0

    def next_batch(self, total_available: int, batch_size: int = 1000) -> tuple[int, int]:
        start = self._last_position
        end = min(start + batch_size, total_available)
        return start, end

    def mark_indexed(self, count: int) -> None:
        self._last_position += count
        self._indexed_count += count

    @property
    def last_position(self) -> int:
        return self._last_position

    @property
    def indexed_count(self) -> int:
        return self._indexed_count

    @property
    def is_complete(self) -> bool:
        return False

    def reset(self) -> None:
        self._last_position = 0
        self._indexed_count = 0
