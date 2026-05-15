from __future__ import annotations

import struct

from .structures import LogRecord

LOG_RECORD_TYPES: dict[int, str] = {
    0x00: "InitializeFileRecord",
    0x01: "DeallocateFileRecord",
    0x02: "WriteEndOfFileRecord",
    0x03: "CreateAttribute",
    0x04: "DeleteAttribute",
    0x05: "UpdateResidentValue",
    0x06: "UpdateNonresidentValue",
    0x07: "UpdateMappingPairs",
    0x08: "DeleteDirtyClusters",
    0x09: "SetNewAttributeSizes",
    0x0A: "AddIndexEntry",
    0x0B: "DeleteIndexEntry",
    0x0C: "SetIndexEntry",
    0x0D: "UpdateRecordData",
    0x0E: "SetIndexEntryV2",
    0x0F: "UpdateRecordDataV2",
    0x10: "UpdateNonresidentValueV2",
}

REDO_OPERATIONS: dict[int, str] = {
    0: "NoOperation",
    1: "CompensationLogRecord",
    2: "InitializeFileRecord",
    3: "DeallocateFileRecord",
    4: "WriteEndOfFileRecord",
    5: "CreateAttribute",
    6: "DeleteAttribute",
    7: "UpdateResidentValue",
    8: "UpdateNonresidentValue",
    9: "UpdateMappingPairs",
    10: "DeleteDirtyClusters",
    11: "SetNewAttributeSizes",
    12: "AddIndexEntry",
    13: "DeleteIndexEntry",
    14: "SetIndexEntry",
    15: "UpdateRecordData",
}

UNDO_OPERATIONS: dict[int, str] = {
    0: "NoOperation",
    1: "CompensationLogRecord",
    2: "InitializeFileRecord",
    3: "DeallocateFileRecord",
    4: "WriteEndOfFileRecord",
    5: "CreateAttribute",
    6: "DeleteAttribute",
    7: "UpdateResidentValue",
    8: "UpdateNonresidentValue",
    9: "UpdateMappingPairs",
    10: "DeleteDirtyClusters",
    11: "SetNewAttributeSizes",
    12: "AddIndexEntry",
    13: "DeleteIndexEntry",
    14: "SetIndexEntry",
    15: "UpdateRecordData",
}


def parse_log_record(data: bytes, offset: int = 0) -> LogRecord | None:
    remaining = len(data) - offset
    if remaining < 48:
        return None

    try:
        lsn = struct.unpack_from("<Q", data, offset + 8)[0]
        prev_lsn = struct.unpack_from("<Q", data, offset + 16)[0]
        client_id = struct.unpack_from("<I", data, offset + 28)[0]
        record_type = struct.unpack_from("<H", data, offset + 32)[0]
        transaction_id = struct.unpack_from("<I", data, offset + 36)[0]
        flags = struct.unpack_from("<H", data, offset + 40)[0]
        record_length = struct.unpack_from("<H", data, offset + 42)[0]
    except struct.error:
        return None

    if record_length < 48 or record_length > remaining:
        record_length = min(remaining, 65536)

    rec = LogRecord(
        lsn=lsn,
        previous_lsn=prev_lsn,
        client_id=client_id,
        record_type=record_type,
        record_type_name=LOG_RECORD_TYPES.get(record_type, f"UNKNOWN_0x{record_type:02X}"),
        transaction_id=transaction_id,
        flags=flags,
        length=record_length,
    )

    if record_length >= 56:
        try:
            redo_op = struct.unpack_from("<H", data, offset + 48)[0]
            undo_op = struct.unpack_from("<H", data, offset + 50)[0]
            rec.redo_operation = REDO_OPERATIONS.get(redo_op, f"REDO_0x{redo_op:02X}")
            rec.undo_operation = UNDO_OPERATIONS.get(undo_op, f"UNDO_0x{undo_op:02X}")
        except struct.error:
            pass

    if record_length >= 64:
        try:
            target_mft = struct.unpack_from("<Q", data, offset + 56)[0]
            rec.target_mft = target_mft
        except struct.error:
            pass

    return rec


def parse_log_records(data: bytes, offset: int = 0, max_records: int = 0) -> list[LogRecord]:
    records: list[LogRecord] = []
    pos = offset
    max_iter = max_records or (len(data) // 48)
    iterations = 0

    while pos + 48 <= len(data) and iterations < max_iter:
        iterations += 1
        record = parse_log_record(data, pos)
        if record is None:
            pos += 48
            continue
        records.append(record)
        if record.length < 48:
            break
        pos += record.length

    return records
