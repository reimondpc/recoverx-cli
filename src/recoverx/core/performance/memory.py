from __future__ import annotations

import threading
from typing import Any


class MemoryPressureGuard:
    def __init__(self, max_memory_mb: float = 512.0, warning_threshold: float = 0.8) -> None:
        self._max_memory = max_memory_mb
        self._warning_threshold = warning_threshold
        self._lock = threading.Lock()
        self._current_usage: float = 0.0
        self._pressure_events: int = 0

    def check(self, estimated_additional_mb: float = 0.0) -> bool:
        with self._lock:
            projected = self._current_usage + estimated_additional_mb
            if projected > self._max_memory:
                self._pressure_events += 1
                return False
            return True

    def record_allocation(self, mb: float) -> None:
        with self._lock:
            self._current_usage += mb

    def record_release(self, mb: float) -> None:
        with self._lock:
            self._current_usage = max(0.0, self._current_usage - mb)

    @property
    def pressure_ratio(self) -> float:
        return self._current_usage / self._max_memory if self._max_memory > 0 else 0.0

    @property
    def is_pressured(self) -> bool:
        return self.pressure_ratio >= self._warning_threshold

    @property
    def pressure_events(self) -> int:
        return self._pressure_events

    def stats(self) -> dict[str, Any]:
        return {
            "max_memory_mb": self._max_memory,
            "current_usage_mb": round(self._current_usage, 1),
            "pressure_ratio": round(self.pressure_ratio, 3),
            "is_pressured": self.is_pressured,
            "pressure_events": self._pressure_events,
        }
