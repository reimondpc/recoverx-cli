from __future__ import annotations

import concurrent.futures
import logging
import threading
from typing import Any, Callable

from recoverx.core.analyzers import AnalysisResult

logger = logging.getLogger("recoverx")


class ParallelAnalyzer:
    def __init__(self, max_workers: int = 4) -> None:
        self._max_workers = max_workers
        self._lock = threading.Lock()
        self._results: list[AnalysisResult] = []

    def run(
        self,
        analyses: list[tuple[Callable[[], list[AnalysisResult]], str]],
    ) -> list[AnalysisResult]:
        self._results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            future_to_name = {executor.submit(fn): name for fn, name in analyses}
            for future in concurrent.futures.as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    result = future.result()
                    with self._lock:
                        self._results.extend(result)
                except Exception as e:
                    logger.error("Analyzer %s failed: %s", name, e)
        return self._results

    @property
    def results(self) -> list[AnalysisResult]:
        return list(self._results)

    @property
    def max_workers(self) -> int:
        return self._max_workers
