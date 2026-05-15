from __future__ import annotations

import logging
from pathlib import Path

from recoverx.core.utils.hashing import sha256
from recoverx.core.utils.raw_reader import RawReader

from .constants import FILE_RECORD_SIGNATURE
from .mft import parse_mft_record
from .runlists.executor import RunlistExecutor
from .runlists.mapping import resolve_runlist, runs_to_byte_offsets
from .runlists.sparse import SparseHandler, is_sparse_runlist
from .runlists.validation import validate_runlist
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
        self._executor = RunlistExecutor(reader, bpb)
        self._sparse_handler = SparseHandler(bpb.cluster_size)

    # ── MFT Walking ──────────────────────────────────────────────────────

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

    # ── Filtering ─────────────────────────────────────────────────────────

    def find_deleted_entries(self, max_records: int = 0) -> list[MFTRecord]:
        all_records = self.walk_mft(max_records)
        return [r for r in all_records if r.is_deleted and not r.is_directory]

    def find_resident_files(self, max_records: int = 0) -> list[MFTRecord]:
        all_records = self.walk_mft(max_records)
        return [r for r in all_records if r.resident and r.data_resident and not r.is_directory]

    def find_non_resident_files(self, max_records: int = 0) -> list[MFTRecord]:
        all_records = self.walk_mft(max_records)
        return [r for r in all_records if r.has_non_resident_data and not r.is_directory]

    def find_fragmented_files(self, max_records: int = 0) -> list[MFTRecord]:
        all_records = self.walk_mft(max_records)
        return [r for r in all_records if r.is_fragmented and not r.is_directory]

    def find_deleted_non_resident(self, max_records: int = 0) -> list[MFTRecord]:
        all_records = self.walk_mft(max_records)
        return [
            r for r in all_records
            if r.is_deleted and r.has_non_resident_data and not r.is_directory
        ]

    # ── Runlist Analysis ──────────────────────────────────────────────────

    def analyse_runs(self, record: MFTRecord) -> dict:
        if not record.has_non_resident_data:
            return {"has_runs": False}

        nr = record.data_non_resident
        assert nr is not None
        resolved = resolve_runlist(nr.data_runs, self.bpb)
        byte_runs = runs_to_byte_offsets(resolved, self.bpb)
        is_sparse = any(r["is_sparse"] for r in byte_runs)

        volume_clusters = self.reader.size // self.bpb.cluster_size
        total_clusters = nr.last_vcn - nr.starting_vcn + 1
        issues = validate_runlist(resolved, total_clusters, volume_clusters)
        circular_issues = self._check_circular(resolved)

        recoverable_bytes, ok_bytes, lost_bytes = (
            self._executor.estimate_recoverable_bytes(resolved, nr.real_size)
        )

        sparse_info = {}
        if is_sparse:
            sparse_info = self._sparse_handler.describe(resolved)

        return {
            "has_runs": True,
            "is_sparse": is_sparse,
            "is_fragmented": len(resolved) > 1,
            "run_count": len(resolved),
            "cluster_size": self.bpb.cluster_size,
            "starting_vcn": nr.starting_vcn,
            "last_vcn": nr.last_vcn,
            "real_size": nr.real_size,
            "allocated_size": nr.allocated_size,
            "initialised_size": nr.initialised_size,
            "byte_runs": byte_runs,
            "resolved_runs": [r.to_dict() for r in resolved],
            "validation_issues": [i.to_dict() for i in issues + circular_issues],
            "recoverable_bytes": recoverable_bytes,
            "recoverable_ok": ok_bytes,
            "recoverable_lost": lost_bytes,
            "sparse_info": sparse_info,
        }

    # ── Non-Resident Recovery ─────────────────────────────────────────────

    def recover_non_resident_file(
        self, record: MFTRecord, max_bytes: int = 0,
    ) -> RecoveredNTFSFile:
        nr = record.data_non_resident
        real_size = nr.real_size if nr else 0

        recovered = RecoveredNTFSFile(
            name=record.name,
            original_name=record.name,
            deleted=record.is_deleted,
            is_directory=record.is_directory,
            mft_record=record.header.mft_record_number,
            file_size=real_size,
            resident=False,
        )

        if not record.has_non_resident_data or nr is None:
            recovered.recovery_status = "no_non_resident_data"
            recovered.recovery_notes.append("File has no non-resident DATA attribute")
            return recovered

        is_sparse = is_sparse_runlist(nr.data_runs)
        is_fragmented = len(nr.data_runs) > 1

        try:
            if is_sparse:
                data = self._executor.execute_sparse_aware(
                    nr.data_runs, real_size, nr.initialised_size, max_bytes,
                )
            else:
                data = self._executor.execute(
                    nr.data_runs, real_size, nr.initialised_size, max_bytes,
                )
        except (ValueError, IndexError, OSError) as e:
            recovered.recovery_status = "execution_error"
            recovered.recovery_notes.append(f"Runlist execution failed: {e}")
            return recovered

        recovered.data = data
        recovered.sha256 = sha256(data)
        recovered.fragmented = is_fragmented
        recovered.sparse = is_sparse
        recovered.run_count = len(nr.data_runs)
        recovered.runs = [
            {
                "vcn": 0,
                "lcn": r.get("cluster_offset", r.get("lcn", 0)),
                "clusters": r["cluster_count"],
            }
            for r in nr.data_runs
        ]

        si = record.standard_info
        recovered.created = str(si.created) if si and si.created else None
        recovered.modified = str(si.modified) if si and si.modified else None
        recovered.mft_modified = str(si.mft_modified) if si and si.mft_modified else None
        recovered.accessed = str(si.accessed) if si and si.accessed else None

        if is_fragmented:
            recovered.recovery_notes.append(
                f"Recovered from {len(nr.data_runs)} fragments"
            )
        if is_sparse:
            recovered.recovery_notes.append("File contains sparse regions")
        if recovered.deleted:
            recovered.recovery_notes.append("Recovered from deleted FILE record")

        recovered.recovery_status = "recovered"
        return recovered

    def classify_recoverability(
        self, record: MFTRecord,
    ) -> str:
        if not record.has_non_resident_data:
            return "not_applicable"

        nr = record.data_non_resident
        assert nr is not None
        resolved = resolve_runlist(nr.data_runs, self.bpb)
        volume_clusters = self.reader.size // self.bpb.cluster_size
        total_clusters = nr.last_vcn - nr.starting_vcn + 1
        issues = validate_runlist(resolved, total_clusters, volume_clusters)

        has_errors = any(i.severity == "error" for i in issues)
        if has_errors:
            return "corrupted"

        _, recoverable, lost = self._executor.estimate_recoverable_bytes(
            resolved, nr.real_size,
        )

        if lost > 0 and recoverable > 0:
            return "partially_recoverable"

        if recoverable == 0:
            return "corrupted"

        return "recoverable"

    # ── Resident Recovery (existing) ──────────────────────────────────────

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

    # ── Saving ────────────────────────────────────────────────────────────

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

    def _check_circular(self, resolved):
        from .runlists.validation import check_circular_runs
        return check_circular_runs(resolved)
