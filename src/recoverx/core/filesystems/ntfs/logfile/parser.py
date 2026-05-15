from __future__ import annotations

import logging
from typing import Any

from recoverx.core.utils.raw_reader import RawReader

from .records import parse_log_records
from .restart_area import find_restart_pages, parse_restart_area
from .structures import LogRecord

logger = logging.getLogger("recoverx")


class LogFileParser:
    def __init__(self, reader: RawReader, bpb: Any) -> None:
        self.reader = reader
        self.bpb = bpb
        self.page_size = 4096

    def parse(self) -> dict:
        data = self._read_logfile()
        if not data:
            return {"found": False, "error": "Could not read $LogFile"}

        restart_pages = find_restart_pages(data)
        restart_areas: list[dict] = []

        for page in restart_pages:
            ra_offset = page.usa_offset + 2 * page.usa_size
            ra = parse_restart_area(data, ra_offset)
            if ra:
                restart_areas.append(ra.to_dict())

        record_pages = self._find_record_pages(data)
        records = self._parse_page_records(data, record_pages)

        return {
            "found": bool(restart_pages or records),
            "page_count": len(data) // self.page_size,
            "page_size": self.page_size,
            "restart_pages": [p.to_dict() for p in restart_pages],
            "restart_areas": restart_areas,
            "records": [r.to_dict() for r in records[:500]],
            "total_records_found": len(records),
            "truncated": len(records) > 500,
        }

    def parse_records(self, max_records: int = 0) -> list[LogRecord]:
        data = self._read_logfile()
        if not data:
            return []
        record_pages = self._find_record_pages(data)
        return self._parse_page_records(data, record_pages, max_records)

    def _read_logfile(self) -> bytes:
        mft_offset = self.bpb.mft_byte_offset
        record_size = self.bpb.bytes_per_file_record
        logfile_ref = 2
        offset = mft_offset + logfile_ref * record_size
        if offset + record_size > self.reader.size:
            return b""
        try:
            raw = self.reader.read_at(offset, record_size)
            from recoverx.core.filesystems.ntfs.mft import parse_mft_record

            record = parse_mft_record(raw, record_size)
            if record and record.data_non_resident:
                from recoverx.core.filesystems.ntfs.runlists.executor import RunlistExecutor

                executor = RunlistExecutor(self.reader, self.bpb)
                return executor.execute(
                    record.data_non_resident.data_runs,
                    record.data_non_resident.real_size,
                )
            elif record and record.data_resident:
                return record.data_resident
        except (ValueError, IndexError, OSError) as e:
            logger.debug("Failed to read $LogFile: %s", e)
        return b""

    @staticmethod
    def _find_record_pages(data: bytes) -> list[int]:
        pages: list[int] = []
        page_size = 4096
        for pos in range(0, len(data), page_size):
            if pos + 4 > len(data):
                break
            if data[pos : pos + 4] == b"RCRD":
                pages.append(pos)
        return pages

    def _parse_page_records(
        self,
        data: bytes,
        page_offsets: list[int],
        max_records: int = 0,
    ) -> list[LogRecord]:
        all_records: list[LogRecord] = []
        for page_offset in page_offsets:
            if max_records and len(all_records) >= max_records:
                break
            page_header_size = 32
            record_start = page_offset + page_header_size
            remaining = max_records - len(all_records) if max_records else 0
            page_records = parse_log_records(data, record_start, remaining)
            all_records.extend(page_records)
        return all_records
