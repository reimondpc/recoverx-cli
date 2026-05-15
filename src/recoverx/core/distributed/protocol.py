from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class TaskMessage:
    task_id: str
    task_type: str
    params: dict[str, Any] = field(default_factory=dict)
    version: str = "1.0"
    sent_at: str = ""
    ttl_seconds: int = 300

    def __post_init__(self) -> None:
        if not self.sent_at:
            self.sent_at = datetime.now().isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "task",
            "task_id": self.task_id,
            "task_type": self.task_type,
            "params": self.params,
            "version": self.version,
            "sent_at": self.sent_at,
            "ttl": self.ttl_seconds,
        }


@dataclass
class ResultMessage:
    task_id: str
    worker_id: str
    status: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    duration_ms: float = 0.0
    sent_at: str = ""

    def __post_init__(self) -> None:
        if not self.sent_at:
            self.sent_at = datetime.now().isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "result",
            "task_id": self.task_id,
            "worker_id": self.worker_id,
            "status": self.status,
            "data": self.data,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "sent_at": self.sent_at,
        }

    @property
    def is_success(self) -> bool:
        return self.status == "completed"

    @property
    def is_error(self) -> bool:
        return self.status == "failed"


@dataclass
class HeartbeatMessage:
    worker_id: str
    status: str = "alive"
    running_tasks: int = 0
    memory_mb: float = 0.0
    cpu_percent: float = 0.0
    sent_at: str = ""

    def __post_init__(self) -> None:
        if not self.sent_at:
            self.sent_at = datetime.now().isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "heartbeat",
            "worker_id": self.worker_id,
            "status": self.status,
            "running_tasks": self.running_tasks,
            "memory_mb": self.memory_mb,
            "cpu_percent": self.cpu_percent,
            "sent_at": self.sent_at,
        }
