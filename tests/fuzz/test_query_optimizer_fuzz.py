"""Fuzz tests for query optimizer, planner, cache, and metrics modules.

Ensures the optimizer never crashes on malformed queries,
extreme parameters, or pathological inputs.
"""

from __future__ import annotations

import random
import string

from recoverx.core.optimizer.cache import QueryCache
from recoverx.core.optimizer.metrics import MetricsCollector, QueryMetrics
from recoverx.core.optimizer.planner import ExecutionStep, QueryPlanner


def _random_string(max_len: int = 30) -> str:
    return "".join(
        random.choice(string.ascii_letters + string.digits + " _=<>!")
        for _ in range(random.randint(0, max_len))
    )


class TestQueryPlannerFuzz:
    def test_plan_empty_query(self):
        planner = QueryPlanner()
        plan = planner.plan("")
        assert plan.original_query == ""
        assert len(plan.steps) >= 1

    def test_plan_garbage_input(self):
        planner = QueryPlanner()
        garbage = [
            " \t\n\r\0\x01\xff",
            "DROP TABLE events; --",
            "' OR 1=1 --",
            "event_type = " + "A" * 10000,
            "\x00\x01\x02\x03\x04\x05",
            "(" * 1000,
            "NULL WHERE 1=1 UNION SELECT * FROM events",
        ]
        for g in garbage:
            planner.plan(g)

    def test_plan_random_strings(self):
        planner = QueryPlanner()
        for _ in range(100):
            s = _random_string(random.randint(0, 50))
            planner.plan(s)

    def test_plan_extreme_values(self):
        planner = QueryPlanner()
        planner.plan("event_type = " * 100)
        planner.plan("timestamp > 9999-12-31 AND timestamp < 0000-01-01")

    def test_plan_all_indexable_fields(self):
        planner = QueryPlanner()
        for field in QueryPlanner.INDEXABLE_FIELDS:
            plan = planner.plan(f"{field} = 'test'")
            assert plan.use_index

    def test_plan_sql_injection_attempts(self):
        planner = QueryPlanner()
        attacks = [
            "event_type = 'x' ; DROP TABLE events",
            "filename = 'x' UNION SELECT * FROM hashes",
            "mft_reference = 0 OR 1=1",
            'source = "x" --',
            "timestamp > '2020' /* comment */",
        ]
        for a in attacks:
            planner.plan(a)

    def test_plan_bounded_recursion(self):
        planner = QueryPlanner()
        deep_query = "event_type = 'x' AND " * 100 + "event_type = 'y'"
        planner.plan(deep_query)
        plan = planner.plan("(" * 100 + "event_type = 'x'" + ")" * 100)
        assert plan is not None


class TestQueryCacheFuzz:
    def test_cache_empty_key(self):
        cache = QueryCache()
        assert cache.get("") is None
        cache.set("", [{"test": 1}])
        result = cache.get("")
        assert result is not None
        assert result[0]["test"] == 1

    def test_cache_garbage_keys(self):
        cache = QueryCache(max_size=10)
        for i in range(100):
            key = _random_string(random.randint(0, 40))
            cache.set(key, [{"i": i}])

    def test_cache_ttl_expiry(self):
        cache = QueryCache(default_ttl=-1.0)
        cache.set("test", [{"x": 1}])
        assert cache.get("test") is None

    def test_cache_max_size(self):
        cache = QueryCache(max_size=5)
        for i in range(100):
            key = f"query_{i}_{_random_string(10)}"
            cache.set(key, [{"i": i}])
        assert cache.size <= 5

    def test_cache_invalidate_missing(self):
        cache = QueryCache()
        assert not cache.invalidate("nonexistent")
        assert not cache.invalidate("")

    def test_cache_clear_preserves_invariants(self):
        cache = QueryCache()
        cache.set("a", [{"v": 1}])
        cache.set("b", [{"v": 2}])
        cache.clear()
        assert cache.size == 0
        assert cache.hit_rate == 0.0

    def test_cache_concurrent_safety(self):
        import threading

        cache = QueryCache(max_size=100)
        errors: list[Exception] = []

        def worker(n: int) -> None:
            for i in range(50):
                key = f"w{n}_q{i}"
                try:
                    cache.set(key, [{"w": n, "i": i}])
                    cache.get(key)
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0

    def test_cache_extreme_values(self):
        cache = QueryCache()
        huge_result = [{"data": "x" * 1000} for _ in range(1000)]
        cache.set("huge", huge_result)
        result = cache.get("huge")
        assert result is not None
        assert len(result) == 1000


class TestMetricsCollectorFuzz:
    def test_metrics_empty(self):
        mc = MetricsCollector()
        s = mc.summary()
        assert s["total_queries"] == 0

    def test_metrics_extreme_durations(self):
        mc = MetricsCollector()
        for d in [0.0, 1e-10, 1e10, -1.0, float("inf"), float("nan")]:
            m = QueryMetrics(duration_ms=d)
            mc.record(m)
        s = mc.summary()
        assert s["total_queries"] == 6

    def test_metrics_clear(self):
        mc = MetricsCollector()
        mc.record(QueryMetrics(duration_ms=10))
        mc.clear()
        assert mc.summary()["total_queries"] == 0

    def test_metrics_many_records(self):
        mc = MetricsCollector()
        for i in range(10000):
            mc.record(QueryMetrics(query=f"q{i}", duration_ms=float(i % 100)))
        s = mc.summary()
        assert s["total_queries"] == 10000

    def test_metrics_cache_stats(self):
        mc = MetricsCollector()
        for i in range(100):
            mc.record(QueryMetrics(query=f"q{i}", cache_hit=(i % 2 == 0)))
        s = mc.summary()
        assert s["cache_hits"] == 50

    def test_metrics_index_usage(self):
        mc = MetricsCollector()
        for i in range(50):
            mc.record(QueryMetrics(query=f"q{i}", index_used=True))
        s = mc.summary()
        assert s["index_usage"] == 50


class TestExecutionStepFuzz:
    def test_all_steps_covered(self):
        steps = list(ExecutionStep)
        assert len(steps) == 6

    def test_plan_cost_bounds(self):
        planner = QueryPlanner()
        plan = planner.plan(
            "event_type = 'FILE_DELETED' AND timestamp > '2020' ORDER BY filename LIMIT 10"
        )
        assert plan.estimated_cost > 0
        assert plan.estimated_rows > 0
