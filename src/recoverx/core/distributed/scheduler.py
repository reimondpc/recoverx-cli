from __future__ import annotations

import logging
import threading
import time
from typing import Any

from .models import Task, TaskPriority, TaskState
from .queue import TaskQueue

logger = logging.getLogger("recoverx")


class Scheduler:
    def __init__(self, queue: TaskQueue, max_concurrent: int = 4) -> None:
        self._queue = queue
        self._max_concurrent = max_concurrent
        self._running: dict[str, threading.Thread] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

    def submit(self, task: Task) -> str:
        if not task.task_id:
            import uuid

            task.task_id = uuid.uuid4().hex[:16]
        self._queue.push(task)
        return task.task_id

    def submit_batch(self, tasks: list[Task]) -> list[str]:
        return [self.submit(t) for t in tasks]

    def schedule(self) -> str | None:
        task = self._queue.pop()
        if task is None:
            return None
        task.state = TaskState.RUNNING
        thread = threading.Thread(target=self._execute, args=(task,), daemon=True)
        with self._lock:
            self._running[task.task_id] = thread
        thread.start()
        return task.task_id

    def _execute(self, task: Task) -> None:
        try:
            logger.debug("Executing task %s (%s)", task.task_id, task.task_type)
            self._run_task(task)
            self._queue.complete(task.task_id)
        except Exception as e:
            logger.error("Task %s failed: %s", task.task_id, e)
            self._queue.fail(task.task_id, str(e))
        finally:
            with self._lock:
                self._running.pop(task.task_id, None)

    def _run_task(self, task: Task) -> None:
        if task.task_type == "index":
            self._do_index(task)
        elif task.task_type == "analyze":
            self._do_analyze(task)
        elif task.task_type == "correlate":
            self._do_correlate(task)
        elif task.task_type == "export":
            self._do_export(task)
        else:
            task.result = {"message": f"Unknown task type: {task.task_type}"}

    def _do_index(self, task: Task) -> None:
        task.result = {"indexed": task.params.get("count", 0), "status": "ok"}

    def _do_analyze(self, task: Task) -> None:
        task.result = {"findings": [], "status": "ok"}

    def _do_correlate(self, task: Task) -> None:
        task.result = {"correlations": 0, "status": "ok"}

    def _do_export(self, task: Task) -> None:
        task.result = {"exported": task.params.get("format", "json"), "status": "ok"}

    def cancel(self, task_id: str) -> bool:
        return self._queue.cancel(task_id)

    def wait_for_all(self, timeout: float | None = None) -> None:
        deadline = time.time() + timeout if timeout else float("inf")
        while time.time() < deadline:
            with self._lock:
                if not self._running:
                    return
            time.sleep(0.1)

    def stop(self) -> None:
        self._stop_event.set()
        self.wait_for_all(timeout=10.0)

    @property
    def running_count(self) -> int:
        return len(self._running)

    @property
    def is_idle(self) -> bool:
        return self.running_count == 0 and self._queue.pending_count() == 0
