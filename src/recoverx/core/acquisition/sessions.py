from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum, auto
from typing import Any

from .targets import AcquisitionTarget
from .transport import TransportInterface


class SessionStatus(Enum):
    PENDING = auto()
    ACTIVE = auto()
    PAUSED = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


class AcquisitionSession:
    def __init__(
        self,
        target: AcquisitionTarget,
        transport: TransportInterface | None = None,
    ) -> None:
        self._session_id = uuid.uuid4().hex[:16]
        self._target = target
        self._transport = transport
        self._status = SessionStatus.PENDING
        self._bytes_acquired = 0
        self._started_at: datetime | None = None
        self._completed_at: datetime | None = None
        self._errors: list[str] = []

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def target(self) -> AcquisitionTarget:
        return self._target

    @property
    def status(self) -> SessionStatus:
        return self._status

    @property
    def bytes_acquired(self) -> int:
        return self._bytes_acquired

    def start(self) -> None:
        self._status = SessionStatus.ACTIVE
        self._started_at = datetime.now()
        self._target.open()

    def pause(self) -> None:
        self._status = SessionStatus.PAUSED

    def resume(self) -> None:
        self._status = SessionStatus.ACTIVE

    def complete(self) -> None:
        self._status = SessionStatus.COMPLETED
        self._completed_at = datetime.now()
        self._target.close()

    def fail(self, error: str) -> None:
        self._status = SessionStatus.FAILED
        self._errors.append(error)
        self._target.close()

    def cancel(self) -> None:
        self._status = SessionStatus.CANCELLED
        self._target.close()

    def record_bytes(self, count: int) -> None:
        self._bytes_acquired += count

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self._session_id,
            "target": self._target.to_dict(),
            "status": self._status.name,
            "bytes_acquired": self._bytes_acquired,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "completed_at": self._completed_at.isoformat() if self._completed_at else None,
            "errors": self._errors,
        }
