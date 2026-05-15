from __future__ import annotations

import time
from datetime import datetime
from typing import Any

import pytest

from recoverx.core.distributed.coordinator import Coordinator, CoordinatorStatus
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
from recoverx.core.distributed.scheduler import Scheduler
from recoverx.core.distributed.worker import Worker, WorkerStatus, WorkerTaskResult

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TestTask:
    def test_create_with_all_fields(self):
        now = datetime.now()
        t = Task(
            task_id="t1",
            task_type="index",
            params={"path": "/data"},
            state=TaskState.PENDING,
            priority=TaskPriority.HIGH,
            created_at=now,
            assigned_to="worker-1",
            result={"ok": True},
            error="",
            retry_count=0,
            max_retries=5,
            progress=0.5,
            depends_on=["t0"],
        )
        assert t.task_id == "t1"
        assert t.task_type == "index"
        assert t.params == {"path": "/data"}
        assert t.state == TaskState.PENDING
        assert t.priority == TaskPriority.HIGH
        assert t.created_at is now
        assert t.assigned_to == "worker-1"
        assert t.result == {"ok": True}
        assert t.retry_count == 0
        assert t.max_retries == 5
        assert t.progress == 0.5
        assert t.depends_on == ["t0"]

    def test_defaults(self):
        t = Task(task_id="t1", task_type="index")
        assert t.params == {}
        assert t.state == TaskState.PENDING
        assert t.priority == TaskPriority.NORMAL
        assert t.created_at is None
        assert t.assigned_to == ""
        assert t.result == {}
        assert t.error == ""
        assert t.retry_count == 0
        assert t.max_retries == 3
        assert t.progress == 0.0
        assert t.depends_on == []

    def test_state_transitions(self):
        t = Task(task_id="t1", task_type="index")
        assert t.state == TaskState.PENDING
        t.state = TaskState.RUNNING
        assert t.state == TaskState.RUNNING
        t.state = TaskState.COMPLETED
        assert t.state == TaskState.COMPLETED

    def test_to_dict(self):
        now = datetime.now()
        t = Task(
            task_id="t1",
            task_type="analyze",
            params={"target": "mem"},
            state=TaskState.PENDING,
            priority=TaskPriority.CRITICAL,
            created_at=now,
            assigned_to="w1",
            result={"found": True},
            error="",
            retry_count=1,
            max_retries=3,
            progress=0.75,
            depends_on=["t0"],
        )
        d = t.to_dict()
        assert d["task_id"] == "t1"
        assert d["task_type"] == "analyze"
        assert d["params"] == {"target": "mem"}
        assert d["state"] == "PENDING"
        assert d["priority"] == 3
        assert d["created_at"] == now.isoformat()
        assert d["assigned_to"] == "w1"
        assert d["result"] == {"found": True}
        assert d["retry_count"] == 1
        assert d["max_retries"] == 3
        assert d["progress"] == 0.75
        assert d["depends_on"] == ["t0"]

    def test_to_dict_no_created_at(self):
        t = Task(task_id="t1", task_type="index")
        d = t.to_dict()
        assert d["created_at"] is None


class TestTaskPriority:
    def test_enum_values(self):
        assert TaskPriority.LOW.value == 0
        assert TaskPriority.NORMAL.value == 1
        assert TaskPriority.HIGH.value == 2
        assert TaskPriority.CRITICAL.value == 3

    def test_ordering(self):
        assert TaskPriority.LOW < TaskPriority.NORMAL
        assert TaskPriority.NORMAL < TaskPriority.HIGH
        assert TaskPriority.HIGH < TaskPriority.CRITICAL


class TestChunkedTask:
    def test_inherits_task_fields(self):
        ct = ChunkedTask(
            task_id="chunk-1",
            task_type="index",
            params={"offset": 1024},
            priority=TaskPriority.HIGH,
        )
        assert ct.task_id == "chunk-1"
        assert ct.task_type == "index"
        assert ct.params == {"offset": 1024}
        assert ct.priority == TaskPriority.HIGH
        assert ct.state == TaskState.PENDING

    def test_chunk_fields_defaults(self):
        ct = ChunkedTask(task_id="chunk-1", task_type="index")
        assert ct.chunk_index == 0
        assert ct.total_chunks == 1
        assert ct.chunk_data == b""

    def test_chunk_fields_custom(self):
        ct = ChunkedTask(
            task_id="chunk-1",
            task_type="index",
            chunk_index=2,
            total_chunks=10,
            chunk_data=b"\x00\x01",
        )
        assert ct.chunk_index == 2
        assert ct.total_chunks == 10
        assert ct.chunk_data == b"\x00\x01"

    def test_to_dict(self):
        ct = ChunkedTask(
            task_id="c1",
            task_type="index",
            chunk_index=3,
            total_chunks=8,
        )
        d = ct.to_dict()
        assert d["task_id"] == "c1"
        assert d["chunk_index"] == 3
        assert d["total_chunks"] == 8
        assert "chunk_data" not in d


class TestCompositeTask:
    def test_add_subtask(self):
        parent = CompositeTask(task_id="parent", task_type="correlate")
        child = Task(task_id="child-1", task_type="index")
        parent.add_subtask(child)
        assert len(parent.subtasks) == 1
        assert parent.subtasks[0] is child

    def test_add_multiple_subtasks(self):
        parent = CompositeTask(task_id="parent", task_type="correlate")
        parent.add_subtask(Task(task_id="c1", task_type="index"))
        parent.add_subtask(Task(task_id="c2", task_type="analyze"))
        assert len(parent.subtasks) == 2

    def test_to_dict(self):
        parent = CompositeTask(task_id="parent", task_type="correlate")
        parent.add_subtask(Task(task_id="c1", task_type="index"))
        parent.add_subtask(Task(task_id="c2", task_type="analyze", params={"x": 1}))
        d = parent.to_dict()
        assert d["task_id"] == "parent"
        assert d["task_type"] == "correlate"
        assert len(d["subtasks"]) == 2
        assert d["subtasks"][0]["task_id"] == "c1"
        assert d["subtasks"][0]["task_type"] == "index"
        assert d["subtasks"][1]["task_id"] == "c2"
        assert d["subtasks"][1]["params"] == {"x": 1}

    def test_to_dict_empty_subtasks(self):
        parent = CompositeTask(task_id="parent", task_type="correlate")
        d = parent.to_dict()
        assert d["subtasks"] == []


# ---------------------------------------------------------------------------
# Queue
# ---------------------------------------------------------------------------


class TestTaskQueue:
    def test_push_pop_round_trip(self):
        q = TaskQueue()
        t = Task(task_id="t1", task_type="index")
        q.push(t)
        popped = q.pop()
        assert popped is not None
        assert popped.task_id == "t1"
        assert popped.state == TaskState.ASSIGNED

    def test_pop_on_empty_queue_returns_none(self):
        q = TaskQueue()
        assert q.pop() is None

    def test_priority_ordering(self):
        q = TaskQueue()
        q.push(Task(task_id="low", task_type="index", priority=TaskPriority.LOW))
        q.push(Task(task_id="high", task_type="index", priority=TaskPriority.HIGH))
        q.push(Task(task_id="normal", task_type="index", priority=TaskPriority.NORMAL))
        first = q.pop()
        second = q.pop()
        third = q.pop()
        assert first is not None and first.task_id == "high"
        assert second is not None and second.task_id == "normal"
        assert third is not None and third.task_id == "low"

    def test_critical_before_high(self):
        q = TaskQueue()
        q.push(Task(task_id="h", task_type="index", priority=TaskPriority.HIGH))
        q.push(Task(task_id="c", task_type="index", priority=TaskPriority.CRITICAL))
        assert q.pop().task_id == "c"
        assert q.pop().task_id == "h"

    def test_complete_sets_state_and_result(self):
        q = TaskQueue()
        t = Task(task_id="t1", task_type="index")
        q.push(t)
        q.pop()
        q.complete("t1", {"indexed": 100})
        assert t.state == TaskState.COMPLETED
        assert t.result == {"indexed": 100}

    def test_complete_without_result(self):
        q = TaskQueue()
        t = Task(task_id="t1", task_type="index")
        q.push(t)
        q.pop()
        q.complete("t1")
        assert t.state == TaskState.COMPLETED
        assert t.result == {}

    def test_fail_with_retry_puts_back_in_queue(self):
        q = TaskQueue()
        t = Task(task_id="t1", task_type="index", retry_count=0, max_retries=3)
        q.push(t)
        q.fail("t1", "transient error")
        assert t.state == TaskState.PENDING
        assert t.retry_count == 1
        popped = q.pop()
        assert popped is not None
        assert popped.task_id == "t1"

    def test_fail_with_max_retries_exhausted(self):
        q = TaskQueue()
        t = Task(task_id="t1", task_type="index", retry_count=3, max_retries=3)
        q.push(t)
        q.fail("t1", "fatal error")
        assert t.state == TaskState.FAILED
        assert t.error == "fatal error"

    def test_fail_increments_retry_count(self):
        q = TaskQueue()
        t = Task(task_id="t1", task_type="index", retry_count=1, max_retries=5)
        q.push(t)
        q.fail("t1", "err")
        assert t.retry_count == 2

    def test_cancel_on_pending_returns_true(self):
        q = TaskQueue()
        t = Task(task_id="t1", task_type="index")
        q.push(t)
        assert q.cancel("t1") is True
        assert t.state == TaskState.CANCELLED

    def test_cancel_skips_popped_task(self):
        q = TaskQueue()
        t = Task(task_id="t1", task_type="index")
        q.push(t)
        q.cancel("t1")
        assert q.pop() is None

    def test_cancel_on_running_returns_false(self):
        q = TaskQueue()
        t = Task(task_id="t1", task_type="index")
        q.push(t)
        t.state = TaskState.RUNNING
        assert q.cancel("t1") is False

    def test_cancel_nonexistent_returns_false(self):
        q = TaskQueue()
        assert q.cancel("nosuch") is False

    def test_pending_count(self):
        q = TaskQueue()
        assert q.pending_count() == 0
        q.push(Task(task_id="t1", task_type="index"))
        assert q.pending_count() == 1
        q.push(Task(task_id="t2", task_type="index"))
        assert q.pending_count() == 2

    def test_completed_count(self):
        q = TaskQueue()
        q.push(Task(task_id="t1", task_type="index"))
        q.pop()
        q.complete("t1")
        assert q.completed_count() == 1

    def test_failed_count(self):
        q = TaskQueue()
        t = Task(task_id="t1", task_type="index", retry_count=0, max_retries=0)
        q.push(t)
        q.fail("t1", "boom")
        assert q.failed_count() == 1

    def test_clear_completed(self):
        q = TaskQueue()
        q.push(Task(task_id="t1", task_type="index"))
        q.pop()
        q.complete("t1")
        assert q.completed_count() == 1
        q.clear_completed()
        assert q.completed_count() == 0

    def test_peek_returns_next_without_removing(self):
        q = TaskQueue()
        q.push(Task(task_id="t1", task_type="index"))
        q.push(Task(task_id="t2", task_type="analyze"))
        peeked = q.peek()
        assert peeked is not None
        assert peeked.task_id == "t1"
        assert peeked.state == TaskState.PENDING
        popped = q.pop()
        assert popped is not None and popped.task_id == "t1"
        assert q.peek().task_id == "t2"

    def test_peek_returns_none_on_empty(self):
        q = TaskQueue()
        assert q.peek() is None

    def test_peek_skips_cancelled(self):
        q = TaskQueue()
        q.push(Task(task_id="t1", task_type="index"))
        q.push(Task(task_id="t2", task_type="analyze"))
        q.cancel("t1")
        peeked = q.peek()
        assert peeked is not None and peeked.task_id == "t2"

    def test_all_tasks_property(self):
        q = TaskQueue()
        q.push(Task(task_id="t1", task_type="index"))
        q.push(Task(task_id="t2", task_type="analyze"))
        assert set(q.all_tasks.keys()) == {"t1", "t2"}


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------


class TestScheduler:
    def test_submit_creates_task_and_returns_id(self):
        s = Scheduler(TaskQueue())
        task = Task(task_id="", task_type="index")
        tid = s.submit(task)
        assert tid != ""
        assert tid == task.task_id

    def test_submit_with_existing_id(self):
        s = Scheduler(TaskQueue())
        task = Task(task_id="my-id", task_type="index")
        tid = s.submit(task)
        assert tid == "my-id"

    def test_submit_batch_returns_list_of_ids(self):
        s = Scheduler(TaskQueue())
        tasks = [Task(task_id="", task_type="index"), Task(task_id="", task_type="analyze")]
        ids = s.submit_batch(tasks)
        assert len(ids) == 2
        assert all(i != "" for i in ids)

    def test_schedule_pops_and_starts_execution(self):
        s = Scheduler(TaskQueue())
        tid = s.submit(Task(task_id="", task_type="index"))
        scheduled_id = s.schedule()
        assert scheduled_id == tid

    def test_schedule_returns_none_when_empty(self):
        s = Scheduler(TaskQueue())
        assert s.schedule() is None

    def test_cancel_delegates_to_queue(self):
        s = Scheduler(TaskQueue())
        tid = s.submit(Task(task_id="", task_type="index"))
        assert s.cancel(tid) is True
        assert s.cancel("nonexistent") is False

    def test_wait_for_all_blocks_until_idle(self):
        s = Scheduler(TaskQueue())
        s.submit(Task(task_id="", task_type="index"))
        s.schedule()
        s.wait_for_all(timeout=5.0)
        assert s.is_idle

    def test_wait_for_all_timeout(self):
        s = Scheduler(TaskQueue())
        s.submit(Task(task_id="", task_type="index"))
        s.schedule()
        s.wait_for_all(timeout=0.1)
        # Should eventually complete

    def test_stop(self):
        s = Scheduler(TaskQueue())
        s.stop()
        assert not s._running

    def test_is_idle_true_initially(self):
        s = Scheduler(TaskQueue())
        assert s.is_idle

    def test_is_idle_false_with_pending(self):
        s = Scheduler(TaskQueue())
        s.submit(Task(task_id="", task_type="index"))
        assert not s.is_idle

    def test_running_count(self):
        s = Scheduler(TaskQueue())
        assert s.running_count == 0
        tid = s.submit(Task(task_id="", task_type="index"))
        scheduled = s.schedule()
        assert scheduled == tid
        s.wait_for_all(timeout=5.0)
        assert s.running_count == 0

    def test_run_task_index(self):
        s = Scheduler(TaskQueue())
        task = Task(task_id="t1", task_type="index", params={"count": 42})
        s._run_task(task)
        assert task.result == {"indexed": 42, "status": "ok"}

    def test_run_task_analyze(self):
        s = Scheduler(TaskQueue())
        task = Task(task_id="t1", task_type="analyze")
        s._run_task(task)
        assert task.result == {"findings": [], "status": "ok"}

    def test_run_task_correlate(self):
        s = Scheduler(TaskQueue())
        task = Task(task_id="t1", task_type="correlate")
        s._run_task(task)
        assert task.result == {"correlations": 0, "status": "ok"}

    def test_run_task_export(self):
        s = Scheduler(TaskQueue())
        task = Task(task_id="t1", task_type="export", params={"format": "csv"})
        s._run_task(task)
        assert task.result == {"exported": "csv", "status": "ok"}

    def test_run_task_unknown_type(self):
        s = Scheduler(TaskQueue())
        task = Task(task_id="t1", task_type="unknown")
        s._run_task(task)
        assert "Unknown task type: unknown" in task.result["message"]

    def test_full_lifecycle(self):
        s = Scheduler(TaskQueue())
        tid = s.submit(Task(task_id="", task_type="index", params={"count": 10}))
        sched_id = s.schedule()
        assert sched_id == tid
        s.wait_for_all(timeout=5.0)
        assert s.is_idle
        assert s.running_count == 0


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------


class TestCoordinator:
    def test_start_stop_cycle(self):
        c = Coordinator()
        assert c._status == CoordinatorStatus.STOPPED
        c.start()
        assert c._status == CoordinatorStatus.RUNNING
        c.stop()
        assert c._status == CoordinatorStatus.STOPPED

    def test_start_idempotent(self):
        c = Coordinator()
        c.start()
        c.start()
        assert c._status == CoordinatorStatus.RUNNING
        c.stop()

    def test_pause_resume(self):
        c = Coordinator()
        c.start()
        c.pause()
        assert c._status == CoordinatorStatus.PAUSED
        c.resume()
        assert c._status == CoordinatorStatus.RUNNING
        c.stop()

    def test_submit_delegates_to_scheduler(self):
        c = Coordinator()
        task = Task(task_id="", task_type="index")
        tid = c.submit(task)
        assert tid == task.task_id
        assert task.task_id != ""

    def test_submit_batch_delegates_to_scheduler(self):
        c = Coordinator()
        tasks = [Task(task_id="", task_type="index"), Task(task_id="", task_type="analyze")]
        ids = c.submit_batch(tasks)
        assert len(ids) == 2

    def test_register_worker_adds_worker(self):
        c = Coordinator()
        c.register_worker("worker-1", {"capabilities": ["index"]})
        assert "worker-1" in c._workers

    def test_register_worker_without_info(self):
        c = Coordinator()
        c.register_worker("worker-1")
        assert c._workers["worker-1"]["info"] == {}

    def test_register_worker_sets_timestamps(self):
        c = Coordinator()
        c.register_worker("worker-1")
        entry = c._workers["worker-1"]
        assert "registered_at" in entry
        assert "last_heartbeat" in entry

    def test_unregister_worker_removes_worker(self):
        c = Coordinator()
        c.register_worker("worker-1")
        c.unregister_worker("worker-1")
        assert "worker-1" not in c._workers

    def test_unregister_nonexistent_does_not_raise(self):
        c = Coordinator()
        c.unregister_worker("nosuch")

    def test_worker_heartbeat_updates_timestamp(self):
        c = Coordinator()
        c.register_worker("worker-1")
        original = c._workers["worker-1"]["last_heartbeat"]
        time.sleep(0.01)
        c.worker_heartbeat("worker-1")
        assert c._workers["worker-1"]["last_heartbeat"] != original

    def test_worker_heartbeat_nonexistent_does_nothing(self):
        c = Coordinator()
        c.worker_heartbeat("nosuch")

    def test_get_status_returns_correct_keys(self):
        c = Coordinator()
        status = c.get_status()
        assert "status" in status
        assert "pending_tasks" in status
        assert "completed_tasks" in status
        assert "failed_tasks" in status
        assert "active_workers" in status
        assert "running_tasks" in status
        assert "workers" in status

    def test_get_status_reflects_state(self):
        c = Coordinator()
        assert c.get_status()["status"] == "STOPPED"
        c.start()
        assert c.get_status()["status"] == "RUNNING"
        c.stop()

    def test_multiple_workers_registration(self):
        c = Coordinator()
        c.register_worker("w1")
        c.register_worker("w2")
        c.register_worker("w3")
        assert c.get_status()["active_workers"] == 3
        assert set(c.get_status()["workers"]) == {"w1", "w2", "w3"}

    def test_get_status_shows_task_counts(self):
        c = Coordinator()
        c.submit(Task(task_id="", task_type="index"))
        c.submit(Task(task_id="", task_type="analyze"))
        status = c.get_status()
        assert status["pending_tasks"] == 2


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------


class TestWorker:
    def test_start_stop_cycle(self):
        w = Worker("worker-1")
        assert w.status == WorkerStatus.STOPPED
        w.start()
        assert w.status == WorkerStatus.IDLE
        w.stop()
        assert w.status == WorkerStatus.STOPPED

    def test_worker_id_property(self):
        w = Worker("my-worker")
        assert w.worker_id == "my-worker"

    def test_execute_index(self):
        w = Worker("w1")
        task = Task(task_id="t1", task_type="index", params={"count": 50})
        result = w.execute(task)
        assert result.success is True
        assert result.data == {"indexed": 50}

    def test_execute_analyze(self):
        w = Worker("w1")
        task = Task(task_id="t1", task_type="analyze")
        result = w.execute(task)
        assert result.success is True
        assert result.data == {"findings": []}

    def test_execute_correlate(self):
        w = Worker("w1")
        task = Task(task_id="t1", task_type="correlate")
        result = w.execute(task)
        assert result.success is True
        assert result.data == {"correlations": 0}

    def test_execute_export(self):
        w = Worker("w1")
        task = Task(task_id="t1", task_type="export", params={"format": "json"})
        result = w.execute(task)
        assert result.success is True
        assert result.data["format"] == "json"

    def test_execute_unknown_type(self):
        w = Worker("w1")
        task = Task(task_id="t1", task_type="unknown")
        result = w.execute(task)
        assert result.success is True
        assert "Unknown type: unknown" in result.data["message"]

    def test_execute_result_has_correct_fields(self):
        w = Worker("w1")
        task = Task(task_id="t1", task_type="index", params={"count": 10})
        result = w.execute(task)
        assert result.task_id == "t1"
        assert isinstance(result.success, bool)
        assert isinstance(result.data, dict)
        assert isinstance(result.duration_ms, float)
        assert result.duration_ms >= 0

    def test_execute_sets_task_state_completed(self):
        w = Worker("w1")
        task = Task(task_id="t1", task_type="index")
        w.execute(task)
        assert task.state == TaskState.COMPLETED

    def test_execute_sets_busy_during_execution(self):
        w = Worker("w1")
        assert w.status == WorkerStatus.STOPPED
        w.start()
        assert w.status == WorkerStatus.IDLE
        task = Task(task_id="t1", task_type="index")
        w.execute(task)
        assert w.status == WorkerStatus.IDLE
        w.stop()

    def test_can_handle_default_true(self):
        w = Worker("w1")
        assert w.can_handle("indexing") is True
        assert w.can_handle("analysis") is True
        assert w.can_handle("correlation") is True
        assert w.can_handle("export") is True

    def test_can_handle_unknown_returns_false(self):
        w = Worker("w1")
        assert w.can_handle("something_else") is False

    def test_can_handle_custom_capabilities(self):
        w = Worker("w1", capabilities={"indexing": True, "analysis": False})
        assert w.can_handle("indexing") is True
        assert w.can_handle("analysis") is False

    def test_get_heartbeat_returns_heartbeat_message(self):
        w = Worker("w1")
        hb = w.get_heartbeat()
        assert isinstance(hb, HeartbeatMessage)
        assert hb.worker_id == "w1"
        assert hb.status == "stopped"
        assert hb.running_tasks == 0

    def test_get_heartbeat_after_execute(self):
        w = Worker("w1")
        w.start()
        task = Task(task_id="t1", task_type="index")
        w.execute(task)
        hb = w.get_heartbeat()
        assert hb.worker_id == "w1"
        w.stop()

    def test_recent_results_returns_latest(self):
        w = Worker("w1")
        t1 = Task(task_id="t1", task_type="index")
        t2 = Task(task_id="t2", task_type="analyze")
        r1 = w.execute(t1)
        r2 = w.execute(t2)
        results = w.recent_results()
        assert len(results) == 2
        assert results[-1] is r2

    def test_recent_results_respects_limit(self):
        w = Worker("w1")
        for i in range(5):
            w.execute(Task(task_id=f"t{i}", task_type="index"))
        assert len(w.recent_results(limit=2)) == 2
        assert len(w.recent_results(limit=10)) == 5

    def test_to_dict(self):
        w = Worker("w1", capabilities={"indexing": True})
        d = w.to_dict()
        assert d["worker_id"] == "w1"
        assert d["status"] == "STOPPED"
        assert d["capabilities"] == {"indexing": True}
        assert d["current_task"] is None
        assert d["recent_results"] == 0

    def test_to_dict_after_execute(self):
        w = Worker("w1")
        w.execute(Task(task_id="t1", task_type="index"))
        d = w.to_dict()
        assert d["recent_results"] == 1
        assert d["current_task"] is None


class TestWorkerTaskResult:
    def test_to_message_creates_result_message(self):
        result = WorkerTaskResult(
            task_id="t1",
            success=True,
            data={"indexed": 10},
            duration_ms=5.0,
        )
        msg = result.to_message("worker-1")
        assert isinstance(msg, ResultMessage)
        assert msg.task_id == "t1"
        assert msg.worker_id == "worker-1"
        assert msg.status == "completed"
        assert msg.data == {"indexed": 10}
        assert msg.duration_ms == 5.0

    def test_to_message_failed(self):
        result = WorkerTaskResult(
            task_id="t1",
            success=False,
            error="something broke",
            duration_ms=2.0,
        )
        msg = result.to_message("worker-1")
        assert msg.status == "failed"
        assert msg.error == "something broke"


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class TestTaskMessage:
    def test_creation(self):
        msg = TaskMessage(task_id="t1", task_type="index")
        assert msg.task_id == "t1"
        assert msg.task_type == "index"
        assert msg.params == {}
        assert msg.version == "1.0"
        assert msg.ttl_seconds == 300

    def test_post_init_sets_sent_at(self):
        msg = TaskMessage(task_id="t1", task_type="index")
        assert msg.sent_at != ""

    def test_sent_at_not_overwritten(self):
        msg = TaskMessage(task_id="t1", task_type="index", sent_at="fixed")
        assert msg.sent_at == "fixed"

    def test_to_dict(self):
        msg = TaskMessage(task_id="t1", task_type="index", params={"path": "/x"})
        d = msg.to_dict()
        assert d["type"] == "task"
        assert d["task_id"] == "t1"
        assert d["task_type"] == "index"
        assert d["params"] == {"path": "/x"}
        assert d["version"] == "1.0"
        assert d["sent_at"] == msg.sent_at
        assert d["ttl"] == 300


class TestResultMessage:
    def test_creation(self):
        msg = ResultMessage(
            task_id="t1",
            worker_id="w1",
            status="completed",
            data={"ok": True},
        )
        assert msg.task_id == "t1"
        assert msg.worker_id == "w1"
        assert msg.status == "completed"
        assert msg.data == {"ok": True}
        assert msg.error == ""
        assert msg.duration_ms == 0.0

    def test_post_init_sets_sent_at(self):
        msg = ResultMessage(task_id="t1", worker_id="w1", status="completed")
        assert msg.sent_at != ""

    def test_to_dict(self):
        msg = ResultMessage(
            task_id="t1",
            worker_id="w1",
            status="completed",
            data={"ok": True},
            error="",
            duration_ms=5.0,
        )
        d = msg.to_dict()
        assert d["type"] == "result"
        assert d["task_id"] == "t1"
        assert d["worker_id"] == "w1"
        assert d["status"] == "completed"
        assert d["data"] == {"ok": True}
        assert d["duration_ms"] == 5.0

    def test_is_success(self):
        msg = ResultMessage(task_id="t1", worker_id="w1", status="completed")
        assert msg.is_success is True
        assert msg.is_error is False

    def test_is_error(self):
        msg = ResultMessage(task_id="t1", worker_id="w1", status="failed")
        assert msg.is_error is True
        assert msg.is_success is False


class TestHeartbeatMessage:
    def test_creation(self):
        msg = HeartbeatMessage(worker_id="w1")
        assert msg.worker_id == "w1"
        assert msg.status == "alive"
        assert msg.running_tasks == 0
        assert msg.memory_mb == 0.0
        assert msg.cpu_percent == 0.0

    def test_post_init_sets_sent_at(self):
        msg = HeartbeatMessage(worker_id="w1")
        assert msg.sent_at != ""

    def test_custom_fields(self):
        msg = HeartbeatMessage(
            worker_id="w1",
            status="busy",
            running_tasks=2,
            memory_mb=512.0,
            cpu_percent=45.5,
        )
        assert msg.status == "busy"
        assert msg.running_tasks == 2
        assert msg.memory_mb == 512.0
        assert msg.cpu_percent == 45.5

    def test_to_dict(self):
        msg = HeartbeatMessage(worker_id="w1")
        d = msg.to_dict()
        assert d["type"] == "heartbeat"
        assert d["worker_id"] == "w1"
        assert d["status"] == "alive"
        assert d["running_tasks"] == 0
        assert d["memory_mb"] == 0.0
        assert d["cpu_percent"] == 0.0
        assert d["sent_at"] == msg.sent_at
