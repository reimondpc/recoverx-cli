from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class LogFileHeader:
    signature: str = ""
    usa_offset: int = 0
    usa_size: int = 0
    last_lsn: int = 0
    major_version: int = 0
    minor_version: int = 0
    file_size: int = 0
    page_size: int = 4096
    valid: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "signature": self.signature,
            "usa_offset": self.usa_offset,
            "usa_size": self.usa_size,
            "last_lsn": self.last_lsn,
            "major_version": self.major_version,
            "minor_version": self.minor_version,
            "file_size": self.file_size,
            "page_size": self.page_size,
            "valid": self.valid,
        }


@dataclass
class RestartArea:
    current_lsn: int = 0
    log_client_lsn: int = 0
    client_prev_lsn: int = 0
    client_next_lsn: int = 0
    restart_area_length: int = 0
    open_log_count: int = 0
    last_lsn: int = 0
    oldest_lsn: int = 0
    valid: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_lsn": self.current_lsn,
            "log_client_lsn": self.log_client_lsn,
            "client_prev_lsn": self.client_prev_lsn,
            "client_next_lsn": self.client_next_lsn,
            "restart_area_length": self.restart_area_length,
            "open_log_count": self.open_log_count,
            "last_lsn": self.last_lsn,
            "oldest_lsn": self.oldest_lsn,
            "valid": self.valid,
        }


@dataclass
class LogRecord:
    lsn: int = 0
    previous_lsn: int = 0
    client_id: int = 0
    record_type: int = 0
    record_type_name: str = ""
    transaction_id: int = 0
    flags: int = 0
    redo_operation: str = ""
    undo_operation: str = ""
    target_attribute: str = ""
    target_mft: int = 0
    redo_data: bytes = b""
    undo_data: bytes = b""
    length: int = 0
    valid: bool = True
    validation_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "lsn": self.lsn,
            "previous_lsn": self.previous_lsn,
            "client_id": self.client_id,
            "record_type": hex(self.record_type),
            "record_type_name": self.record_type_name,
            "transaction_id": self.transaction_id,
            "flags": hex(self.flags),
            "redo_operation": self.redo_operation,
            "undo_operation": self.undo_operation,
            "target_attribute": self.target_attribute,
            "target_mft": self.target_mft,
            "length": self.length,
            "valid": self.valid,
        }
