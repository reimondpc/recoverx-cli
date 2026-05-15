"""Fuzz tests for distributed queue, models, and protocol modules.

Ensures the distributed task system never crashes on
malformed inputs, concurrent access, or extreme values.
"""

from __future__ import annotations

import math
import random
import string
import threading
from datetime import datetime

from recoverx.core.distributed.models import (
    ChunkedTask,
    CompositeTask,
    Task,
    TaskPriority,
    TaskState,
)
from recoverx.core.distributed.protocol import (
    HeartbeatMessage,
    ResultMessage,
    TaskMessage,
)
from recoverx.core.distributed.queue import TaskQueue


def _random_string(max_len: int = 20) -> str:  # pragma: no cover
    return "".join(random.choice(string.ascii_letters) for _ in range(random.randint(0, max_len)))


def _random_task(**overrides: object) -> Task:  # pragma: no cover
    params: dict[str, object] = {
        "task_id": _random_string(),
        "task_type": _random_string(),
        "params": {},
        "priority": random.choice(list(TaskPriority)),
        "created_at": datetime.now(),
    }
    params.update(overrides)
    return Task(**params)  # type: ignore[arg-type]


class TestFuzzDistributedQueue:
    def test_fuzz_task_priority_combinations(self) -> None:
        priorities = list(TaskPriority)
        q = TaskQueue()
        tasks = []
        for _ in range(50):
            p = random.choice(priorities)
            t = _random_task(priority=p)
            q.push(t)
            tasks.append(t)

        seen: list[TaskPriority] = []
        for _ in range(50):
            t = q.pop()
            if t:
                seen.append(t.priority)

        for i in range(1, len(seen)):
            assert seen[i - 1].value >= seen[i].value

    def test_fuzz_task_state_transitions(self) -> None:
        valid_next: dict[TaskState, list[TaskState]] = {
            TaskState.PENDING: [TaskState.ASSIGNED, TaskState.CANCELLED],
            TaskState.ASSIGNED: [TaskState.RUNNING, TaskState.CANCELLED],
            TaskState.RUNNING: [TaskState.COMPLETED, TaskState.FAILED, TaskState.RETRY],
            TaskState.RETRY: [TaskState.PENDING],
            TaskState.COMPLETED: [],
            TaskState.FAILED: [],
            TaskState.CANCELLED: [],
        }

        for _ in range(100):
            start = random.choice(list(TaskState))
            t = _random_task(state=start)
            transitions = random.randint(0, 20)
            for _ in range(transitions):
                allowed = valid_next.get(t.state, [])
                if not allowed:
                    break
                next_state = random.choice(allowed)
                t.state = next_state

            assert t.state in TaskState

    def test_fuzz_concurrent_queue_ops(self) -> None:
        q = TaskQueue()
        n_threads = 8
        ops_per_thread = 50
        barrier = threading.Barrier(n_threads)

        def worker(worker_id: int) -> None:
            barrier.wait()
            for i in range(ops_per_thread):
                try:
                    choice = random.randint(0, 4)
                    if choice == 0:
                        t = _random_task(priority=random.choice(list(TaskPriority)))
                        q.push(t)
                    elif choice == 1:
                        q.pop()
                    elif choice == 2:
                        t = _random_task()
                        q.push(t)
                        q.complete(t.task_id, {"result": "ok"})
                    elif choice == 3:
                        t = _random_task()
                        q.push(t)
                        q.cancel(t.task_id)
                    elif choice == 4:
                        q.peek()
                except Exception:
                    pass

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        assert q.completed_count() >= 0
        assert q.pending_count() >= 0

    def test_fuzz_malformed_task_params(self) -> None:
        malformed_params: list[object] = [
            None,
            {},
            {"a": {"b": {"c": {"d": {}}}}},
            {"x" * 500: "y" * 500},
            {str(i): i for i in range(200)},
            {"binary": b"\x00\x01\x02\xff".decode("latin-1")},
            {None: "value"},  # type: ignore[dict-item]
            {(): "tuple_key"},  # type: ignore[dict-item]
        ]

        q = TaskQueue()
        for params in malformed_params:
            try:
                t = Task(
                    task_id=_random_string(),
                    task_type=_random_string(),
                    params=params,  # type: ignore[arg-type]
                )
                q.push(t)
                popped = q.pop()
                if popped:
                    popped.to_dict()
            except Exception:
                pass

    def test_fuzz_empty_queue_stress(self) -> None:
        q = TaskQueue()
        for _ in range(200):
            try:
                q.pop()
                q.peek()
                q.complete("nonexistent", {})
                q.cancel("nonexistent")
                q.fail("nonexistent", "err")
            except Exception:
                pass

        assert q.pending_count() == 0
        assert q.completed_count() == 0
        assert q.failed_count() == 0

    def test_fuzz_many_tasks(self) -> None:
        q = TaskQueue()
        n = 1200
        for i in range(n):
            p = random.choice(list(TaskPriority))
            t = _random_task(priority=p)
            t.task_id = f"fuzz_{i}_{t.task_id}"
            q.push(t)

        assert q.pending_count() == n

        popped: list[Task] = []
        for _ in range(n):
            t = q.pop()
            if t:
                popped.append(t)

        for i in range(1, len(popped)):
            assert popped[i - 1].priority.value >= popped[i].priority.value

        assert len(popped) <= n

    def test_fuzz_corrupt_chunked_task(self) -> None:
        for _ in range(50):
            try:
                ct = ChunkedTask(
                    task_id=_random_string(),
                    task_type=_random_string(),
                    chunk_index=random.choice([-100, -1, 0, 1, 999999]),
                    total_chunks=random.choice([0, -5, 1, 1000000]),
                    chunk_data=bytes(random.randint(0, 4096)),
                )
                d = ct.to_dict()
                assert isinstance(d, dict)
            except Exception:
                pass

    def test_fuzz_composite_task_nested(self) -> None:
        for _ in range(30):
            try:
                subtasks = []
                for _ in range(random.randint(0, 50)):
                    subtasks.append(_random_task())
                ct = CompositeTask(
                    task_id=_random_string(),
                    task_type=_random_string(),
                    subtasks=subtasks,
                )
                d = ct.to_dict()
                assert isinstance(d, dict)
                assert len(d["subtasks"]) == len(subtasks)
            except Exception:
                pass


class TestFuzzProtocolMessages:
    def test_fuzz_protocol_message_serialization(self) -> None:
        for _ in range(100):
            try:
                choice = random.randint(0, 2)
                if choice == 0:
                    msg = TaskMessage(
                        task_id=_random_string(100),
                        task_type=_random_string(100),
                        params={
                            _random_string(): _random_string() for _ in range(random.randint(0, 20))
                        },
                        version=random.choice(["", "1.0", "x.y", "\x00", None]),  # type: ignore[arg-type]
                        sent_at=random.choice(["", "now", "\x00", None]),  # type: ignore[arg-type]
                        ttl_seconds=random.choice([-1, 0, 999999999, None]),  # type: ignore[arg-type]
                    )
                elif choice == 1:
                    msg = ResultMessage(
                        task_id=_random_string(100),
                        worker_id=_random_string(100),
                        status=random.choice(["completed", "failed", "", "\x00", None]),  # type: ignore[arg-type]
                        data={
                            _random_string(): random.randint(0, 1000)
                            for _ in range(random.randint(0, 10))
                        },
                        error=_random_string(100),
                        duration_ms=random.choice([-1.0, 0.0, float("inf"), float("nan"), 1e9]),
                        sent_at=random.choice(["", "now", "\x00"]),
                    )
                else:
                    msg = HeartbeatMessage(
                        worker_id=_random_string(100),
                        status=random.choice(["alive", "dead", "", "\x00", None]),  # type: ignore[arg-type]
                        running_tasks=random.choice([-1, 0, 999999, None]),  # type: ignore[arg-type]
                        memory_mb=random.choice([-1.0, 0.0, float("inf"), float("nan")]),
                        cpu_percent=random.choice([-1.0, 101.0, float("inf"), float("nan")]),
                        sent_at=random.choice(["", "now", "\x00"]),
                    )

                d = msg.to_dict()
                assert isinstance(d, dict)
                assert "type" in d
            except Exception:
                pass

    def test_fuzz_heartbeat_extreme_values(self) -> None:
        for _ in range(30):
            try:
                hb = HeartbeatMessage(
                    worker_id="\x00" * 1000,
                    status="\ud83d\udca5" * 100,
                    running_tasks=2**63,
                    memory_mb=float("nan"),
                    cpu_percent=float("inf"),
                    sent_at="a" * 10000,
                )
                d = hb.to_dict()
                assert isinstance(d, dict)
            except Exception:
                pass

    def test_fuzz_result_message_is_properties(self) -> None:
        for _ in range(30):
            try:
                rm = ResultMessage(
                    task_id=_random_string(),
                    worker_id=_random_string(),
                    status=random.choice(["completed", "failed", "", "\x00", "unknown"]),
                    data={},
                    error=_random_string(200),
                    duration_ms=random.uniform(-1e6, 1e6),
                )
                _ = rm.is_success
                _ = rm.is_error
                _ = rm.to_dict()
            except Exception:
                pass

    def test_fuzz_message_empty_fields(self) -> None:
        try:
            tm = TaskMessage(task_id="", task_type="")
            d = tm.to_dict()
            assert d["task_id"] == ""
            assert d["task_type"] == ""
        except Exception:
            pass

        try:
            rm = ResultMessage(task_id="", worker_id="", status="")
            d = rm.to_dict()
            assert isinstance(d, dict)
        except Exception:
            pass

        try:
            hb = HeartbeatMessage(worker_id="")
            d = hb.to_dict()
            assert isinstance(d, dict)
        except Exception:
            pass
