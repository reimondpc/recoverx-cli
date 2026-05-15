from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class QueryMetrics:
    query: str = ""
    duration_ms: float = 0.0
    rows_returned: int = 0
    rows_scanned: int = 0
    cache_hit: bool = False
    planner_cost: float = 0.0
    index_used: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query[:100],
            "duration_ms": round(self.duration_ms, 2),
            "rows_returned": self.rows_returned,
            "rows_scanned": self.rows_scanned,
            "cache_hit": self.cache_hit,
            "planner_cost": self.planner_cost,
            "index_used": self.index_used,
        }


class MetricsCollector:
    def __init__(self) -> None:
        self._metrics: list[QueryMetrics] = []

    def record(self, metric: QueryMetrics) -> None:
        self._metrics.append(metric)

    def collect(self, query: str) -> QueryMetrics:
        m = QueryMetrics(query=query)
        start = time.time()
        return m

    def finalize(self, metric: QueryMetrics) -> None:
        self._metrics.append(metric)

    def summary(self) -> dict[str, Any]:
        if not self._metrics:
            return {"total_queries": 0}
        durations = [m.duration_ms for m in self._metrics]
        cache_hits = sum(1 for m in self._metrics if m.cache_hit)
        return {
            "total_queries": len(self._metrics),
            "avg_duration_ms": round(sum(durations) / len(durations), 2),
            "max_duration_ms": round(max(durations), 2),
            "min_duration_ms": round(min(durations), 2),
            "cache_hits": cache_hits,
            "cache_hit_rate": round(cache_hits / len(self._metrics), 3),
            "index_usage": sum(1 for m in self._metrics if m.index_used),
        }

    def clear(self) -> None:
        self._metrics.clear()
