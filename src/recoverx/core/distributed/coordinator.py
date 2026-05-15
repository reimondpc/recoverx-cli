from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from enum import Enum, auto
from typing import Any

from .models import Task, TaskState
from .queue import TaskQueue
from .scheduler import Scheduler

logger = logging.getLogger("recoverx")


class CoordinatorStatus(Enum):
    STOPPED = auto()
    RUNNING = auto()
    PAUSED = auto()
    ERROR = auto()


class Coordinator:
    def __init__(self, max_concurrent: int = 4) -> None:
        self._queue = TaskQueue()
        self._scheduler = Scheduler(self._queue, max_concurrent)
        self._workers: dict[str, dict[str, Any]] = {}
        self._status = CoordinatorStatus.STOPPED
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._status == CoordinatorStatus.RUNNING:
            return
        self._status = CoordinatorStatus.RUNNING
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Coordinator started")

    def stop(self) -> None:
        self._status = CoordinatorStatus.STOPPED
        self._scheduler.stop()
        logger.info("Coordinator stopped")

    def pause(self) -> None:
        self._status = CoordinatorStatus.PAUSED

    def resume(self) -> None:
        self._status = CoordinatorStatus.RUNNING

    def submit(self, task: Task) -> str:
        return self._scheduler.submit(task)

    def submit_batch(self, tasks: list[Task]) -> list[str]:
        return self._scheduler.submit_batch(tasks)

    def register_worker(self, worker_id: str, info: dict[str, Any] | None = None) -> None:
        with self._lock:
            self._workers[worker_id] = {
                "id": worker_id,
                "info": info or {},
                "registered_at": datetime.now().isoformat(),
                "last_heartbeat": datetime.now().isoformat(),
            }

    def unregister_worker(self, worker_id: str) -> None:
        with self._lock:
            self._workers.pop(worker_id, None)

    def worker_heartbeat(self, worker_id: str) -> None:
        with self._lock:
            if worker_id in self._workers:
                self._workers[worker_id]["last_heartbeat"] = datetime.now().isoformat()

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "status": self._status.name,
                "pending_tasks": self._queue.pending_count(),
                "completed_tasks": self._queue.completed_count(),
                "failed_tasks": self._queue.failed_count(),
                "active_workers": len(self._workers),
                "running_tasks": self._scheduler.running_count,
                "workers": list(self._workers.keys()),
            }

    def _run_loop(self) -> None:
        while self._status == CoordinatorStatus.RUNNING:
            if self._scheduler.running_count < self._scheduler._max_concurrent:
                self._scheduler.schedule()
            time.sleep(0.1)
