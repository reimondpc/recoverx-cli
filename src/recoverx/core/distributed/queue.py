from __future__ import annotations

import heapq
import threading
from typing import Any

from .models import Task, TaskPriority, TaskState


class TaskQueue:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._queue: list[tuple[int, int, Task]] = []
        self._counter = 0
        self._all_tasks: dict[str, Task] = {}
        self._completed: dict[str, Task] = {}

    def push(self, task: Task) -> None:
        with self._lock:
            priority_val = -task.priority.value
            self._counter += 1
            heapq.heappush(self._queue, (priority_val, self._counter, task))
            self._all_tasks[task.task_id] = task

    def pop(self) -> Task | None:
        with self._lock:
            while self._queue:
                _, _, task = heapq.heappop(self._queue)
                if task.state == TaskState.CANCELLED:
                    continue
                if task.state == TaskState.PENDING:
                    task.state = TaskState.ASSIGNED
                    return task
            return None

    def peek(self) -> Task | None:
        with self._lock:
            for _, _, task in self._queue:
                if task.state == TaskState.PENDING:
                    return task
            return None

    def complete(self, task_id: str, result: dict[str, Any] | None = None) -> None:
        with self._lock:
            task = self._all_tasks.get(task_id)
            if task:
                task.state = TaskState.COMPLETED
                if result:
                    task.result = result
                self._completed[task_id] = task

    def fail(self, task_id: str, error: str = "") -> None:
        with self._lock:
            task = self._all_tasks.get(task_id)
            if task:
                if task.retry_count < task.max_retries:
                    task.retry_count += 1
                    task.state = TaskState.PENDING
                    self._counter += 1
                    heapq.heappush(self._queue, (-task.priority.value, self._counter, task))
                else:
                    task.state = TaskState.FAILED
                    task.error = error

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            task = self._all_tasks.get(task_id)
            if task and task.state in (TaskState.PENDING, TaskState.ASSIGNED):
                task.state = TaskState.CANCELLED
                return True
            return False

    def get(self, task_id: str) -> Task | None:
        return self._all_tasks.get(task_id)

    def pending_count(self) -> int:
        with self._lock:
            return sum(1 for t in self._all_tasks.values() if t.state == TaskState.PENDING)

    def completed_count(self) -> int:
        return len(self._completed)

    def failed_count(self) -> int:
        with self._lock:
            return sum(1 for t in self._all_tasks.values() if t.state == TaskState.FAILED)

    def clear_completed(self) -> None:
        with self._lock:
            self._completed.clear()

    @property
    def all_tasks(self) -> dict[str, Task]:
        return dict(self._all_tasks)
