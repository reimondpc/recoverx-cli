from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, IntEnum, auto
from typing import Any


class TaskState(Enum):
    PENDING = auto()
    ASSIGNED = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()
    RETRY = auto()


class TaskPriority(IntEnum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Task:
    task_id: str
    task_type: str
    params: dict[str, Any] = field(default_factory=dict)
    state: TaskState = TaskState.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    created_at: datetime | None = None
    assigned_to: str = ""
    result: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    retry_count: int = 0
    max_retries: int = 3
    progress: float = 0.0
    depends_on: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "params": self.params,
            "state": self.state.name,
            "priority": self.priority.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "assigned_to": self.assigned_to,
            "result": self.result,
            "error": self.error,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "progress": self.progress,
            "depends_on": self.depends_on,
        }


@dataclass
class ChunkedTask(Task):
    chunk_index: int = 0
    total_chunks: int = 1
    chunk_data: bytes = b""

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base["chunk_index"] = self.chunk_index
        base["total_chunks"] = self.total_chunks
        return base


@dataclass
class CompositeTask(Task):
    subtasks: list[Task] = field(default_factory=list)

    def add_subtask(self, task: Task) -> None:
        self.subtasks.append(task)

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base["subtasks"] = [t.to_dict() for t in self.subtasks]
        return base
