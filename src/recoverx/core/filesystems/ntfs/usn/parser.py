from __future__ import annotations

import logging
from typing import Any

from recoverx.core.utils.raw_reader import RawReader

from .records import parse_usn_records
from .structures import USNJournalInfo, USNRecord

logger = logging.getLogger("recoverx")

USN_JOURNAL_ATTR = b"$J"
USN_MAX_ATTR = b"$Max"

USN_PAGE_SIZE = 4096


class USNParser:
    def __init__(self, reader: RawReader, bpb: Any) -> None:
        self.reader = reader
        self.bpb = bpb
        self.cluster_size = bpb.cluster_size

    def find_usn_journal(self) -> tuple[list[dict], list[dict]] | None:
        max_info = self._parse_max()
        j_records = self._parse_j()
        if max_info or j_records:
            return max_info, j_records
        return None

    def _parse_max(self) -> list[dict]:
        max_data = self._find_max_data()
        if not max_data:
            return []
        info = USNJournalInfo()
        if len(max_data) >= 32:
            info.major_version = int.from_bytes(max_data[0:4], "little")
            info.minor_version = int.from_bytes(max_data[4:8], "little")
            info.usn_page_size = int.from_bytes(max_data[24:28], "little")
            info.allocation_delta = int.from_bytes(max_data[28:32], "little")
        if len(max_data) >= 40:
            info.max_usn = int.from_bytes(max_data[32:40], "little", signed=True)
        return [info.to_dict()]

    def _parse_j(self) -> list[dict]:
        j_data = self._find_j_data()
        if not j_data:
            return []
        records = parse_usn_records(j_data)
        return [r.to_dict() for r in records]

    def parse_raw(self) -> list[USNRecord]:
        j_data = self._find_j_data()
        if not j_data:
            return []
        return parse_usn_records(j_data)

    def _find_max_data(self) -> bytes:
        from recoverx.core.filesystems.ntfs.mft import parse_mft_record

        mft_offset = self.bpb.mft_byte_offset
        record_size = self.bpb.bytes_per_file_record
        extend_ref = 11
        offset = mft_offset + extend_ref * record_size
        if offset + record_size > self.reader.size:
            return b""
        try:
            data = self.reader.read_at(offset, record_size)
            record = parse_mft_record(data, record_size)
            if record and record.data_non_resident:
                from recoverx.core.filesystems.ntfs.runlists.executor import RunlistExecutor

                executor = RunlistExecutor(self.reader, self.bpb)
                fn_size = record.file_name.real_size if record.file_name else 0
                return executor.execute(record.data_non_resident.data_runs, fn_size)
        except (ValueError, IndexError, OSError):
            pass
        return b""

    def _find_j_data(self) -> bytes:
        from recoverx.core.filesystems.ntfs.mft import parse_mft_record

        mft_offset = self.bpb.mft_byte_offset
        record_size = self.bpb.bytes_per_file_record
        extend_ref = 11
        offset = mft_offset + extend_ref * record_size
        if offset + record_size > self.reader.size:
            return b""
        try:
            data = self.reader.read_at(offset, record_size)
            record = parse_mft_record(data, record_size)
            if record:
                from recoverx.core.filesystems.ntfs.attributes import (
                    NonResidentAttribute,
                    parse_attribute_header,
                )

                attr_offset = record.header.attrs_offset
                for attr in record.attributes:
                    parsed = parse_attribute_header(data, attr_offset)
                    if isinstance(parsed, NonResidentAttribute) and parsed.attr_type == 0x80:
                        from recoverx.core.filesystems.ntfs.runlists.executor import (
                            RunlistExecutor,
                        )

                        executor = RunlistExecutor(self.reader, self.bpb)
                        return executor.execute(parsed.data_runs, parsed.real_size)
                    attr_offset += attr.length
        except (ValueError, IndexError, OSError):
            pass
        return b""
