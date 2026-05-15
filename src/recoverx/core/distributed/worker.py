from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any

from .models import Task, TaskState
from .protocol import HeartbeatMessage, ResultMessage, TaskMessage

logger = logging.getLogger("recoverx")


class WorkerStatus(Enum):
    IDLE = auto()
    BUSY = auto()
    ERROR = auto()
    STOPPED = auto()


@dataclass
class WorkerTaskResult:
    task_id: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    duration_ms: float = 0.0

    def to_message(self, worker_id: str) -> ResultMessage:
        return ResultMessage(
            task_id=self.task_id,
            worker_id=worker_id,
            status="completed" if self.success else "failed",
            data=self.data,
            error=self.error,
            duration_ms=self.duration_ms,
        )


class Worker:
    def __init__(self, worker_id: str, capabilities: dict[str, bool] | None = None) -> None:
        self._worker_id = worker_id
        self._status = WorkerStatus.STOPPED
        self._current_task: Task | None = None
        self._capabilities = capabilities or {
            "indexing": True,
            "analysis": True,
            "correlation": True,
            "export": True,
        }
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._results: list[WorkerTaskResult] = []

    @property
    def worker_id(self) -> str:
        return self._worker_id

    @property
    def status(self) -> WorkerStatus:
        return self._status

    def start(self) -> None:
        self._status = WorkerStatus.IDLE
        self._thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._thread.start()
        logger.info("Worker %s started", self._worker_id)

    def stop(self) -> None:
        self._status = WorkerStatus.STOPPED
        logger.info("Worker %s stopped", self._worker_id)

    def execute(self, task: Task) -> WorkerTaskResult:
        start = time.time()
        self._current_task = task
        self._status = WorkerStatus.BUSY
        try:
            task.state = TaskState.RUNNING
            if task.task_type == "index":
                result_data = {"indexed": task.params.get("count", 0)}
            elif task.task_type == "analyze":
                result_data = {"findings": []}
            elif task.task_type == "correlate":
                result_data = {"correlations": 0}
            elif task.task_type == "export":
                result_data = {"format": task.params.get("format", "json"), "path": "output"}
            else:
                result_data = {"message": f"Unknown type: {task.task_type}"}
            duration = (time.time() - start) * 1000
            result = WorkerTaskResult(
                task_id=task.task_id, success=True, data=result_data, duration_ms=duration
            )
            task.state = TaskState.COMPLETED
            self._results.append(result)
            return result
        except Exception as e:
            duration = (time.time() - start) * 1000
            result = WorkerTaskResult(
                task_id=task.task_id, success=False, error=str(e), duration_ms=duration
            )
            task.state = TaskState.FAILED
            self._results.append(result)
            return result
        finally:
            self._current_task = None
            self._status = WorkerStatus.IDLE

    def can_handle(self, task_type: str) -> bool:
        return self._capabilities.get(task_type, False)

    def get_heartbeat(self) -> HeartbeatMessage:
        return HeartbeatMessage(
            worker_id=self._worker_id,
            status=self._status.name.lower(),
            running_tasks=1 if self._current_task else 0,
        )

    def recent_results(self, limit: int = 10) -> list[WorkerTaskResult]:
        return self._results[-limit:]

    def _heartbeat_loop(self) -> None:
        while self._status != WorkerStatus.STOPPED:
            time.sleep(5.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_id": self._worker_id,
            "status": self._status.name,
            "capabilities": self._capabilities,
            "current_task": self._current_task.task_id if self._current_task else None,
            "recent_results": len(self._results),
        }
