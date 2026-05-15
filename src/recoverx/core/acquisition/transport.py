from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChunkResult:
    success: bool
    data: bytes = b""
    error: str = ""
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class TransportInterface(ABC):
    @abstractmethod
    def connect(self, endpoint: str) -> bool: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def send_chunk(self, chunk: bytes) -> ChunkResult: ...

    @abstractmethod
    def receive_chunk(self) -> ChunkResult: ...

    @abstractmethod
    def is_connected(self) -> bool: ...


class LocalTransport(TransportInterface):
    def __init__(self) -> None:
        self._connected = False
        self._buffer: list[bytes] = []

    def connect(self, endpoint: str = "") -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False
        self._buffer.clear()

    def send_chunk(self, chunk: bytes) -> ChunkResult:
        if not self._connected:
            return ChunkResult(success=False, error="Not connected")
        self._buffer.append(chunk)
        return ChunkResult(success=True, metadata={"buffer_size": len(self._buffer)})

    def receive_chunk(self) -> ChunkResult:
        if not self._connected:
            return ChunkResult(success=False, error="Not connected")
        if not self._buffer:
            return ChunkResult(success=True, data=b"")
        data = self._buffer.pop(0)
        return ChunkResult(success=True, data=data)

    def is_connected(self) -> bool:
        return self._connected
