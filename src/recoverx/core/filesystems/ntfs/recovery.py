from __future__ import annotations

import logging
from pathlib import Path

from recoverx.core.utils.hashing import sha256
from recoverx.core.utils.raw_reader import RawReader

from .constants import FILE_RECORD_SIGNATURE
from .mft import parse_mft_record
from .structures import (
    MFTRecord,
    NTFSBootSector,
    RecoveredNTFSFile,
)

logger = logging.getLogger("recoverx")


class NTFSRecovery:
    def __init__(self, reader: RawReader, bpb: NTFSBootSector) -> None:
        self.reader = reader
        self.bpb = bpb
        self._record_size = bpb.bytes_per_file_record

    def walk_mft(self, max_records: int = 0) -> list[MFTRecord]:
        records: list[MFTRecord] = []
        mft_offset = self.bpb.mft_byte_offset
        record_size = self._record_size

        total_records = max_records or (self.reader.size - mft_offset) // record_size
        total_records = min(total_records, 100000)

        for i in range(total_records):
            rec_offset = mft_offset + i * record_size
            if rec_offset + record_size > self.reader.size:
                break

            try:
                data = self.reader.read_at(rec_offset, record_size)
                if len(data) < record_size:
                    break

                if data[0:4] != FILE_RECORD_SIGNATURE:
                    continue

                record = parse_mft_record(data, record_size)
                if record:
                    records.append(record)
            except (ValueError, IndexError, OSError):
                continue

        return records

    def find_deleted_entries(self, max_records: int = 0) -> list[MFTRecord]:
        all_records = self.walk_mft(max_records)
        return [r for r in all_records if r.is_deleted and not r.is_directory]

    def find_resident_files(self, max_records: int = 0) -> list[MFTRecord]:
        all_records = self.walk_mft(max_records)
        return [r for r in all_records if r.resident and r.data_resident and not r.is_directory]

    def recover_resident_file(self, record: MFTRecord) -> RecoveredNTFSFile:
        recovered = RecoveredNTFSFile(
            name=record.name,
            original_name=record.name,
            deleted=record.is_deleted,
            is_directory=record.is_directory,
            mft_record=record.header.mft_record_number,
            file_size=len(record.data_resident or b""),
            resident=True,
            data=record.data_resident or b"",
        )

        if not record.data_resident:
            recovered.recovery_status = "no_resident_data"
            recovered.recovery_notes.append("File has no resident DATA attribute")
            return recovered

        recovered.data = record.data_resident
        recovered.sha256 = sha256(recovered.data)
        si = record.standard_info
        recovered.created = str(si.created) if si and si.created else None
        recovered.modified = str(si.modified) if si and si.modified else None
        recovered.mft_modified = str(si.mft_modified) if si and si.mft_modified else None
        recovered.accessed = str(si.accessed) if si and si.accessed else None
        recovered.recovery_status = "recovered"

        if recovered.deleted:
            recovered.recovery_notes.append("Recovered from deleted FILE record")

        return recovered

    def save_recovered(self, recovered: RecoveredNTFSFile, output_dir: str = "recovered") -> str:
        out = Path(output_dir) / "ntfs_recovery"
        out.mkdir(parents=True, exist_ok=True)

        base_name = recovered.name or f"mft_{recovered.mft_record}"
        safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in base_name)

        if recovered.deleted:
            safe_name = f"DELETED_{safe_name}"

        if not safe_name:
            safe_name = f"recovered_mft_{recovered.mft_record}"

        filepath = out / safe_name
        filepath.write_bytes(recovered.data)
        return str(filepath)

    @staticmethod
    def detect(reader: RawReader) -> bool:
        if reader.size < 512:
            return False
        sector0 = reader.read_at(0, 512)
        return sector0[3:11] == b"NTFS    "
