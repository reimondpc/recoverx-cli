"""Shared forensic data collection helpers for CLI commands."""

from __future__ import annotations

from recoverx.core.filesystems.ntfs.recovery import NTFSRecovery
from recoverx.core.filesystems.ntfs.structures import NTFSBootSector
from recoverx.core.filesystems.ntfs.usn.mapping import map_usn_records
from recoverx.core.filesystems.ntfs.usn.parser import USNParser
from recoverx.core.forensics.events import file_created, file_deleted, file_modified
from recoverx.core.forensics.models import EventSource, ForensicEvent
from recoverx.core.utils.raw_reader import RawReader


def collect_mft_events(reader: RawReader, bpb: NTFSBootSector) -> list[ForensicEvent]:
    rec = NTFSRecovery(reader, bpb)
    records = rec.walk_mft(max_records=500)
    events: list[ForensicEvent] = []
    for r in records[:200]:
        if r.is_directory:
            continue
        si = r.standard_info
        fn = r.file_name
        fname = r.name or ""

        if si and si.created:
            events.append(
                file_created(
                    si.created,
                    fname,
                    r.header.mft_record_number,
                    fn.parent_mft if fn else 0,
                    fn.real_size if fn else 0,
                    source=EventSource.MFT,
                )
            )
        if si and si.modified and si.created != si.modified:
            events.append(
                file_modified(
                    si.modified,
                    fname,
                    r.header.mft_record_number,
                    fn.real_size if fn else 0,
                    source=EventSource.MFT,
                )
            )
        if r.is_deleted:
            events.append(
                file_deleted(
                    None,
                    fname,
                    r.header.mft_record_number,
                    fn.parent_mft if fn else 0,
                    source=EventSource.MFT,
                    notes=["MFT record marked as deleted"],
                )
            )
    return events


def collect_usn_events(reader: RawReader, bpb: NTFSBootSector) -> list[ForensicEvent]:
    try:
        usn_parser = USNParser(reader, bpb)
        records = usn_parser.parse_raw()
        if not records:
            return []
        return map_usn_records(records)
    except (ValueError, IndexError, OSError) as e:
        import logging

        logging.getLogger("recoverx").debug("USN collection failed: %s", e)
        return []
