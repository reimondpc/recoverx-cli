from __future__ import annotations

import threading
from datetime import datetime, timezone

import pytest

from recoverx.core.analyzers.base import AnalysisResult, FindingSeverity
from recoverx.core.performance.incremental import IncrementalIndexer
from recoverx.core.performance.memory import MemoryPressureGuard
from recoverx.core.performance.parallel import ParallelAnalyzer
from recoverx.core.performance.streaming import StreamingIndexer


class TestStreamingIndexer:
    def test_creation_defaults(self):
        idx = StreamingIndexer()
        assert idx.batch_size == 1000
        assert idx.processed == 0
        assert idx.buffered == 0

    def test_creation_custom_values(self):
        idx = StreamingIndexer(batch_size=50, max_memory_mb=128.0)
        assert idx.batch_size == 50
        assert idx.processed == 0
        assert idx.buffered == 0

    def test_add_returns_none_below_batch_size(self):
        idx = StreamingIndexer(batch_size=5)
        result = idx.add({"id": 1})
        assert result is None

    def test_add_flushes_at_batch_threshold(self):
        idx = StreamingIndexer(batch_size=3)
        idx.add({"id": 1})
        result = idx.add({"id": 2})
        assert result is None
        result = idx.add({"id": 3})
        assert result == 3
        assert idx.buffered == 0

    def test_flush_returns_count_and_clears_buffer(self):
        idx = StreamingIndexer(batch_size=100)
        idx.add({"id": 1})
        idx.add({"id": 2})
        count = idx.flush()
        assert count == 2
        assert idx.buffered == 0

    def test_processed_accumulates(self):
        idx = StreamingIndexer(batch_size=2)
        idx.add({"id": 1})
        idx.add({"id": 2})
        idx.add({"id": 3})
        idx.add({"id": 4})
        assert idx.processed == 4

    def test_processed_tracks_flush(self):
        idx = StreamingIndexer(batch_size=10)
        idx.add({"id": 1})
        assert idx.processed == 0
        idx.flush()
        assert idx.processed == 1

    def test_batch_size_property(self):
        idx = StreamingIndexer(batch_size=42)
        assert idx.batch_size == 42

    def test_buffered_property(self):
        idx = StreamingIndexer(batch_size=10)
        assert idx.buffered == 0
        idx.add({"id": 1})
        assert idx.buffered == 1
        idx.add({"id": 2})
        assert idx.buffered == 2


class TestIncrementalIndexer:
    def test_next_batch_from_zero(self):
        idx = IncrementalIndexer()
        start, end = idx.next_batch(total_available=100, batch_size=10)
        assert start == 0
        assert end == 10

    def test_next_batch_limited_by_total(self):
        idx = IncrementalIndexer()
        start, end = idx.next_batch(total_available=5, batch_size=10)
        assert start == 0
        assert end == 5

    def test_mark_indexed_advances_position(self):
        idx = IncrementalIndexer()
        idx.mark_indexed(10)
        assert idx.last_position == 10
        assert idx.indexed_count == 10

    def test_next_batch_after_mark_indexed(self):
        idx = IncrementalIndexer()
        idx.mark_indexed(50)
        start, end = idx.next_batch(total_available=100, batch_size=30)
        assert start == 50
        assert end == 80

    def test_last_position_default(self):
        idx = IncrementalIndexer()
        assert idx.last_position == 0

    def test_indexed_count_default(self):
        idx = IncrementalIndexer()
        assert idx.indexed_count == 0

    def test_indexed_count_accumulates(self):
        idx = IncrementalIndexer()
        idx.mark_indexed(5)
        idx.mark_indexed(3)
        assert idx.indexed_count == 8

    def test_is_complete_returns_false(self):
        idx = IncrementalIndexer()
        assert idx.is_complete is False

    def test_reset_clears_state(self):
        idx = IncrementalIndexer()
        idx.mark_indexed(25)
        idx.reset()
        assert idx.last_position == 0
        assert idx.indexed_count == 0


class TestParallelAnalyzer:
    def test_max_workers_property(self):
        pa = ParallelAnalyzer(max_workers=8)
        assert pa.max_workers == 8

    def test_run_with_empty_analyses(self):
        pa = ParallelAnalyzer()
        results = pa.run([])
        assert results == []

    def test_results_property(self):
        pa = ParallelAnalyzer()
        assert pa.results == []

    def test_run_with_successful_analyses(self):
        pa = ParallelAnalyzer(max_workers=2)

        def make_a(n):
            def fn():
                return [
                    AnalysisResult(
                        analyzer_name=f"a{n}",
                        severity=FindingSeverity.MEDIUM,
                        confidence=0.8,
                        description=f"result from a{n}",
                    )
                ]

            return fn

        results = pa.run([(make_a(1), "a1"), (make_a(2), "a2")])
        assert len(results) == 2
        names = {r.analyzer_name for r in results}
        assert names == {"a1", "a2"}

    def test_run_handles_failing_analyzers(self):
        pa = ParallelAnalyzer(max_workers=2)

        def good():
            return [
                AnalysisResult(
                    analyzer_name="good",
                    severity=FindingSeverity.INFO,
                    confidence=1.0,
                    description="ok",
                )
            ]

        def bad():
            raise RuntimeError("analyzer crashed")

        results = pa.run([(good, "good"), (bad, "bad")])
        assert len(results) == 1
        assert results[0].analyzer_name == "good"

    def test_results_returns_copy(self):
        pa = ParallelAnalyzer()
        r1 = pa.results
        r2 = pa.results
        assert r1 is not r2


class TestMemoryPressureGuard:
    def test_check_returns_true_when_below_max(self):
        guard = MemoryPressureGuard(max_memory_mb=100.0)
        assert guard.check(estimated_additional_mb=50.0) is True

    def test_check_returns_false_when_exceeded(self):
        guard = MemoryPressureGuard(max_memory_mb=100.0)
        guard.record_allocation(80.0)
        assert guard.check(estimated_additional_mb=30.0) is False

    def test_check_false_without_extra_when_already_over(self):
        guard = MemoryPressureGuard(max_memory_mb=100.0)
        guard.record_allocation(150.0)
        assert guard.check() is False

    def test_record_allocation_increases_usage(self):
        guard = MemoryPressureGuard(max_memory_mb=1000.0)
        guard.record_allocation(50.0)
        guard.record_allocation(25.0)
        s = guard.stats()
        assert s["current_usage_mb"] == 75.0

    def test_record_release_decreases_usage(self):
        guard = MemoryPressureGuard(max_memory_mb=1000.0)
        guard.record_allocation(100.0)
        guard.record_release(30.0)
        s = guard.stats()
        assert s["current_usage_mb"] == 70.0

    def test_record_release_never_below_zero(self):
        guard = MemoryPressureGuard(max_memory_mb=1000.0)
        guard.record_release(50.0)
        s = guard.stats()
        assert s["current_usage_mb"] == 0.0

    def test_pressure_ratio_zero_when_no_usage(self):
        guard = MemoryPressureGuard(max_memory_mb=100.0)
        assert guard.pressure_ratio == 0.0

    def test_pressure_ratio_calculation(self):
        guard = MemoryPressureGuard(max_memory_mb=200.0)
        guard.record_allocation(50.0)
        assert guard.pressure_ratio == 0.25

    def test_is_pressured_at_threshold(self):
        guard = MemoryPressureGuard(max_memory_mb=100.0, warning_threshold=0.8)
        guard.record_allocation(80.0)
        assert guard.is_pressured is True

    def test_is_pressured_below_threshold(self):
        guard = MemoryPressureGuard(max_memory_mb=100.0, warning_threshold=0.8)
        guard.record_allocation(79.9)
        assert guard.is_pressured is False

    def test_is_pressured_above_threshold(self):
        guard = MemoryPressureGuard(max_memory_mb=100.0, warning_threshold=0.8)
        guard.record_allocation(81.0)
        assert guard.is_pressured is True

    def test_pressure_events_counter(self):
        guard = MemoryPressureGuard(max_memory_mb=100.0)
        guard.record_allocation(90.0)
        guard.check(estimated_additional_mb=20.0)
        guard.check(estimated_additional_mb=20.0)
        assert guard.pressure_events == 2

    def test_pressure_events_not_incremented_on_success(self):
        guard = MemoryPressureGuard(max_memory_mb=100.0)
        guard.check(estimated_additional_mb=10.0)
        assert guard.pressure_events == 0

    def test_stats_dict(self):
        guard = MemoryPressureGuard(max_memory_mb=512.0, warning_threshold=0.8)
        guard.record_allocation(128.0)
        guard.check(estimated_additional_mb=500.0)  # triggers pressure
        s = guard.stats()
        assert s["max_memory_mb"] == 512.0
        assert s["current_usage_mb"] == 128.0
        assert s["pressure_ratio"] == 0.25
        assert s["is_pressured"] is False
        assert s["pressure_events"] == 1
