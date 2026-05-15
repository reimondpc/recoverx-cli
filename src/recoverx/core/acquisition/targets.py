from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any


class TargetType(Enum):
    LOCAL_FILE = auto()
    LOCAL_DEVICE = auto()
    REMOTE_FILE = auto()
    REMOTE_DEVICE = auto()
    MEMORY_DUMP = auto()
    NETWORK_STREAM = auto()
    CLOUD_SNAPSHOT = auto()


@dataclass
class TargetMetadata:
    size_bytes: int = 0
    sector_size: int = 512
    filesystem: str = ""
    device_model: str = ""
    serial_number: str = ""
    acquired_at: str = ""
    hash_sha256: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "size_bytes": self.size_bytes,
            "sector_size": self.sector_size,
            "filesystem": self.filesystem,
            "device_model": self.device_model,
            "serial_number": self.serial_number,
            "acquired_at": self.acquired_at,
            "hash_sha256": self.hash_sha256,
            "notes": self.notes,
        }


class AcquisitionTarget:
    def __init__(
        self,
        path: str,
        target_type: TargetType = TargetType.LOCAL_FILE,
        metadata: TargetMetadata | None = None,
    ) -> None:
        self._path = path
        self._target_type = target_type
        self._metadata = metadata or TargetMetadata()
        self._read_only = True
        self._opened = False

    @property
    def path(self) -> str:
        return self._path

    @property
    def target_type(self) -> TargetType:
        return self._target_type

    @property
    def metadata(self) -> TargetMetadata:
        return self._metadata

    @property
    def is_read_only(self) -> bool:
        return self._read_only

    def open(self) -> None:
        self._opened = True

    def close(self) -> None:
        self._opened = False

    def validate(self) -> list[str]:
        issues: list[str] = []
        if not self._path:
            issues.append("Target path is empty")
        return issues

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self._path,
            "type": self._target_type.name,
            "metadata": self._metadata.to_dict(),
            "read_only": self._read_only,
            "opened": self._opened,
        }
