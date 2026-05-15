from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest

from recoverx.core.optimizer.cache import CachedResult, QueryCache
from recoverx.core.optimizer.metrics import MetricsCollector, QueryMetrics
from recoverx.core.optimizer.planner import (
    ExecutionStep,
    QueryPlan,
    QueryPlanner,
    optimize_sql,
)


class TestQueryPlan:
    def test_defaults(self):
        plan = QueryPlan()
        assert plan.original_query == ""
        assert plan.steps == []
        assert plan.estimated_rows == 0
        assert plan.use_index is False
        assert plan.index_columns == []
        assert plan.optimized_sql == ""
        assert plan.estimated_cost == 0.0

    def test_add_step(self):
        plan = QueryPlan()
        plan.add_step(ExecutionStep.INDEX_SCAN)
        assert plan.steps == [ExecutionStep.INDEX_SCAN]

    def test_to_dict(self):
        plan = QueryPlan(
            original_query="SELECT * FROM events",
            estimated_rows=100,
            use_index=True,
            index_columns=["event_type"],
            optimized_sql="SELECT * FROM events",
            estimated_cost=1.5,
        )
        plan.add_step(ExecutionStep.FILTER_PUSHDOWN)
        plan.add_step(ExecutionStep.INDEX_SCAN)
        d = plan.to_dict()
        assert d["steps"] == ["FILTER_PUSHDOWN", "INDEX_SCAN"]
        assert d["estimated_rows"] == 100
        assert d["use_index"] is True
        assert d["index_columns"] == ["event_type"]
        assert d["estimated_cost"] == 1.5


class TestQueryPlanner:
    def test_plan_returns_query_plan(self):
        planner = QueryPlanner()
        plan = planner.plan("SELECT * FROM events")
        assert isinstance(plan, QueryPlan)
        assert plan.original_query == "SELECT * FROM events"

    def test_filter_pushdown_always_added(self):
        planner = QueryPlanner()
        plan = planner.plan("SELECT * FROM events")
        assert ExecutionStep.FILTER_PUSHDOWN in plan.steps

    def test_index_scan_for_known_fields(self):
        planner = QueryPlanner()
        plan = planner.plan("SELECT * FROM events WHERE event_type = 'create'")
        assert ExecutionStep.INDEX_SCAN in plan.steps
        assert "event_type" in plan.index_columns

    def test_index_scan_for_multiple_fields(self):
        planner = QueryPlanner()
        plan = planner.plan("SELECT * FROM events WHERE event_type = 'x' AND source = 'y'")
        assert plan.steps.count(ExecutionStep.INDEX_SCAN) >= 2

    def test_table_scan_for_unknown_field(self):
        planner = QueryPlanner()
        plan = planner.plan(
            "SELECT * FROM events WHERE event_type = 'x'",
            available_indexes=set(),
        )
        # Planner scans all INDEXABLE_FIELDS; event_type not in available_indexes → TABLE_SCAN
        assert ExecutionStep.TABLE_SCAN in plan.steps

    def test_sort_added_for_order_by(self):
        planner = QueryPlanner()
        plan = planner.plan("SELECT * FROM events ORDER BY timestamp")
        assert ExecutionStep.SORT in plan.steps

    def test_sort_added_for_sort_keyword(self):
        planner = QueryPlanner()
        plan = planner.plan("SELECT * FROM events SORT BY timestamp")
        assert ExecutionStep.SORT in plan.steps

    def test_limit_step(self):
        planner = QueryPlanner()
        plan = planner.plan("SELECT * FROM events LIMIT 10")
        assert ExecutionStep.LIMIT in plan.steps

    def test_aggregate_for_count(self):
        planner = QueryPlanner()
        plan = planner.plan("SELECT count(*) FROM events")
        assert ExecutionStep.AGGREGATE in plan.steps

    def test_aggregate_for_sum(self):
        planner = QueryPlanner()
        plan = planner.plan("SELECT sum(size) FROM events")
        assert ExecutionStep.AGGREGATE in plan.steps

    def test_estimated_rows_event_type_query(self):
        planner = QueryPlanner()
        plan = planner.plan("SELECT * FROM events WHERE event_type = 'x'")
        assert plan.estimated_rows == 1000

    def test_estimated_rows_timestamp_query(self):
        planner = QueryPlanner()
        plan = planner.plan("SELECT * FROM events WHERE timestamp > '2024-01-01'")
        assert plan.estimated_rows == 5000

    def test_estimated_rows_default(self):
        planner = QueryPlanner()
        plan = planner.plan("SELECT * FROM events")
        assert plan.estimated_rows == 10000

    def test_estimated_cost_without_index(self):
        planner = QueryPlanner()
        plan = planner.plan(
            "SELECT * FROM events WHERE event_type = 'x'",
            available_indexes=set(),
        )
        # FILTER_PUSHDOWN (0.5) + TABLE_SCAN (10.0) = 10.5
        assert plan.estimated_cost == 10.5

    def test_estimated_cost_with_index(self):
        planner = QueryPlanner()
        plan = planner.plan("SELECT * FROM events WHERE event_type = 'x'")
        # FILTER_PUSHDOWN (0.5) + INDEX_SCAN (1.0) = 1.5
        assert plan.estimated_cost == 1.5

    def test_estimated_cost_full_pipeline(self):
        planner = QueryPlanner()
        plan = planner.plan(
            "SELECT count(*) FROM events WHERE event_type = 'x' ORDER BY timestamp LIMIT 5"
        )
        # FILTER_PUSHDOWN (0.5) + INDEX_SCAN × 2 (2.0) + SORT (5.0) + LIMIT (0.1) + AGGREGATE (2.0)
        assert plan.estimated_cost == 9.6

    def test_rewrite_preserves_query(self):
        planner = QueryPlanner()
        sql = "SELECT * FROM events WHERE event_type = ?"
        plan = planner.plan(sql, available_indexes={"event_type"})
        assert plan.optimized_sql == sql

    def test_optimize_sql_convenience(self):
        result = optimize_sql("SELECT * FROM events WHERE event_type = 'x'")
        assert isinstance(result, str)


class TestCachedResult:
    def test_is_expired_false_when_fresh(self):
        entry = CachedResult(
            query="test",
            result=[],
            cached_at=time.time(),
            ttl_seconds=60.0,
        )
        assert not entry.is_expired

    def test_is_expired_true_when_stale(self):
        entry = CachedResult(
            query="test",
            result=[],
            cached_at=time.time() - 100,
            ttl_seconds=10.0,
        )
        assert entry.is_expired


class TestQueryCache:
    def test_set_and_get_round_trip(self):
        cache = QueryCache()
        cache.set("SELECT * FROM events", [{"id": 1}])
        result = cache.get("SELECT * FROM events")
        assert result == [{"id": 1}]

    def test_get_returns_none_for_unknown(self):
        cache = QueryCache()
        assert cache.get("SELECT * FROM nowhere") is None

    def test_get_returns_none_for_expired_entry(self):
        cache = QueryCache(default_ttl=-1.0)
        cache.set("SELECT * FROM events", [{"id": 1}])
        time.sleep(0.01)
        assert cache.get("SELECT * FROM events") is None

    def test_ttl_parameter_overrides_default(self):
        cache = QueryCache(default_ttl=60.0)
        cache.set("SELECT * FROM events", [{"id": 1}], ttl=-1.0)
        time.sleep(0.01)
        assert cache.get("SELECT * FROM events") is None

    def test_invalidate_removes_entry(self):
        cache = QueryCache()
        cache.set("q1", [1])
        assert cache.invalidate("q1") is True
        assert cache.get("q1") is None

    def test_invalidate_returns_false_for_missing(self):
        cache = QueryCache()
        assert cache.invalidate("no-such-query") is False

    def test_clear_resets_all_state(self):
        cache = QueryCache()
        cache.set("q1", [1])
        cache.set("q2", [2])
        cache.get("q1")  # hit
        cache.get("q3")  # miss
        cache.clear()
        assert cache.size == 0
        assert cache.stats["hits"] == 0
        assert cache.stats["misses"] == 0

    def test_hit_rate_zero_when_empty(self):
        cache = QueryCache()
        assert cache.hit_rate == 0.0

    def test_hit_rate_calculation(self):
        cache = QueryCache()
        cache.set("q1", [1])
        cache.get("q1")  # hit
        cache.get("q2")  # miss
        assert cache.hit_rate == 0.5

    def test_stats_dict(self):
        cache = QueryCache(max_size=500, default_ttl=30.0)
        cache.set("q1", [1])
        cache.get("q1")
        s = cache.stats
        assert s["size"] == 1
        assert s["max_size"] == 500
        assert s["hits"] == 1
        assert s["misses"] == 0
        assert s["hit_rate"] == 1.0
        assert s["default_ttl"] == 30.0

    def test_lru_eviction(self):
        cache = QueryCache(max_size=2)
        cache.set("q1", [1])
        cache.set("q2", [2])
        cache.set("q3", [3])
        assert cache.size == 2
        assert cache.get("q1") is None

    def test_normalization_makes_keys_case_insensitive(self):
        cache = QueryCache()
        cache.set("SELECT * FROM EVENTS", [{"id": 1}])
        assert cache.get("select * from events") == [{"id": 1}]

    def test_thread_safety(self):
        import random
        import threading

        cache = QueryCache(max_size=100)
        errors = []

        def worker(n):
            try:
                for i in range(50):
                    k = f"query-{random.randint(0, 20)}"
                    cache.set(k, [{"n": n, "i": i}])
                    cache.get(k)
                    cache.invalidate(k)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors, f"thread safety errors: {errors}"


class TestQueryMetrics:
    def test_defaults(self):
        m = QueryMetrics()
        assert m.query == ""
        assert m.duration_ms == 0.0
        assert m.rows_returned == 0
        assert m.rows_scanned == 0
        assert m.cache_hit is False
        assert m.planner_cost == 0.0
        assert m.index_used is False

    def test_to_dict_truncates_long_query(self):
        m = QueryMetrics(query="x" * 200, duration_ms=1.234)
        d = m.to_dict()
        assert len(d["query"]) == 100
        assert d["duration_ms"] == 1.23


class TestMetricsCollector:
    def test_record_adds_metric(self):
        c = MetricsCollector()
        m = QueryMetrics(query="q1", duration_ms=10.0)
        c.record(m)
        assert c.summary()["total_queries"] == 1

    def test_summary_empty(self):
        c = MetricsCollector()
        assert c.summary() == {"total_queries": 0}

    def test_summary_with_metrics(self):
        c = MetricsCollector()
        c.record(QueryMetrics(query="q1", duration_ms=10.0, cache_hit=True, index_used=True))
        c.record(QueryMetrics(query="q2", duration_ms=20.0, cache_hit=False, index_used=False))
        s = c.summary()
        assert s["total_queries"] == 2
        assert s["avg_duration_ms"] == 15.0
        assert s["max_duration_ms"] == 20.0
        assert s["min_duration_ms"] == 10.0
        assert s["cache_hits"] == 1
        assert s["cache_hit_rate"] == 0.5
        assert s["index_usage"] == 1

    def test_clear_resets(self):
        c = MetricsCollector()
        c.record(QueryMetrics(query="q1"))
        c.clear()
        assert c.summary()["total_queries"] == 0

    def test_collect_returns_metric(self):
        c = MetricsCollector()
        m = c.collect("SELECT * FROM events")
        assert isinstance(m, QueryMetrics)
        assert m.query == "SELECT * FROM events"

    def test_finalize_appends_metric(self):
        c = MetricsCollector()
        m = QueryMetrics(query="q1")
        c.finalize(m)
        assert c.summary()["total_queries"] == 1
