from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class NTFSBootSector:
    bytes_per_sector: int = 512
    sectors_per_cluster: int = 1
    total_sectors: int = 0
    mft_cluster: int = 0
    mft_mirror_cluster: int = 0
    clusters_per_file_record: int = 0
    clusters_per_index_block: int = 0
    volume_serial: str = ""
    media_descriptor: int = 0xF8
    oem_id: str = "NTFS"
    signature_valid: bool = False

    @property
    def cluster_size(self) -> int:
        return self.bytes_per_sector * self.sectors_per_cluster

    @property
    def bytes_per_file_record(self) -> int:
        if self.clusters_per_file_record >= 0:
            return self.cluster_size << self.clusters_per_file_record
        return self.cluster_size >> (-self.clusters_per_file_record)

    @property
    def mft_byte_offset(self) -> int:
        return self.mft_cluster * self.cluster_size

    @property
    def total_size(self) -> int:
        return self.total_sectors * self.bytes_per_sector

    def to_dict(self) -> dict:
        return {
            "type": "NTFS",
            "bytes_per_sector": self.bytes_per_sector,
            "sectors_per_cluster": self.sectors_per_cluster,
            "cluster_size": self.cluster_size,
            "total_sectors": self.total_sectors,
            "total_size": self.total_size,
            "mft_cluster": self.mft_cluster,
            "mft_byte_offset": self.mft_byte_offset,
            "mft_mirror_cluster": self.mft_mirror_cluster,
            "bytes_per_file_record": self.bytes_per_file_record,
            "clusters_per_index_block": self.clusters_per_index_block,
            "volume_serial": self.volume_serial,
            "oem_id": self.oem_id,
            "signature_valid": self.signature_valid,
        }


@dataclass
class MFTRecordHeader:
    signature: str = ""
    fixup_offset: int = 0
    fixup_count: int = 0
    log_sequence_number: int = 0
    sequence_number: int = 0
    link_count: int = 0
    attrs_offset: int = 0
    flags: int = 0
    used_size: int = 0
    allocated_size: int = 0
    mft_record_number: int = 0

    @property
    def in_use(self) -> bool:
        return bool(self.flags & 0x0001)

    @property
    def is_directory(self) -> bool:
        return bool(self.flags & 0x0002)

    @property
    def is_deleted(self) -> bool:
        return not self.in_use

    def to_dict(self) -> dict:
        return {
            "signature": self.signature,
            "sequence_number": self.sequence_number,
            "link_count": self.link_count,
            "flags": self.flags,
            "in_use": self.in_use,
            "is_directory": self.is_directory,
            "is_deleted": self.is_deleted,
            "attrs_offset": self.attrs_offset,
            "used_size": self.used_size,
            "mft_record_number": self.mft_record_number,
        }


def _ntfs_timestamp_to_datetime(ts: int) -> datetime | None:
    if ts == 0:
        return None
    try:
        from datetime import timedelta
        return datetime(1601, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=ts // 10)
    except (OverflowError, ValueError):
        return None


@dataclass
class StandardInformation:
    created: datetime | None = None
    modified: datetime | None = None
    mft_modified: datetime | None = None
    accessed: datetime | None = None
    flags: int = 0
    max_version: int = 0
    version: int = 0
    class_id: int = 0
    owner_id: int = 0
    security_id: int = 0
    quota_charged: int = 0
    usn: int = 0

    def to_dict(self) -> dict:
        return {
            "created": self.created.isoformat() if self.created else None,
            "modified": self.modified.isoformat() if self.modified else None,
            "mft_modified": self.mft_modified.isoformat() if self.mft_modified else None,
            "accessed": self.accessed.isoformat() if self.accessed else None,
            "flags": self.flags,
        }


@dataclass
class FileNameAttribute:
    parent_mft: int = 0
    parent_seq: int = 0
    created: datetime | None = None
    modified: datetime | None = None
    mft_modified: datetime | None = None
    accessed: datetime | None = None
    allocated_size: int = 0
    real_size: int = 0
    flags: int = 0
    reparse: int = 0
    name_length: int = 0
    name_type: int = 0
    name: str = ""

    def to_dict(self) -> dict:
        return {
            "parent_mft": self.parent_mft,
            "created": self.created.isoformat() if self.created else None,
            "modified": self.modified.isoformat() if self.modified else None,
            "accessed": self.accessed.isoformat() if self.accessed else None,
            "allocated_size": self.allocated_size,
            "real_size": self.real_size,
            "flags": self.flags,
            "name": self.name,
            "name_type": self.name_type,
        }


@dataclass
class NTFSAttribute:
    attr_type: int = 0
    attr_type_name: str = ""
    length: int = 0
    non_resident: bool = False
    name_length: int = 0
    name_offset: int = 0
    name: str = ""
    flags: int = 0
    attr_id: int = 0

    def to_dict(self) -> dict:
        return {
            "attr_type": self.attr_type,
            "attr_type_name": self.attr_type_name,
            "length": self.length,
            "non_resident": self.non_resident,
            "name": self.name,
            "flags": self.flags,
        }


@dataclass
class ResidentAttribute(NTFSAttribute):
    value_length: int = 0
    value_offset: int = 0
    data: bytes = b""

    def to_dict(self) -> dict:
        base = super().to_dict()
        base["resident"] = True
        base["value_length"] = self.value_length
        return base


@dataclass
class NonResidentAttribute(NTFSAttribute):
    starting_vcn: int = 0
    last_vcn: int = 0
    runlist_offset: int = 0
    compression_unit: int = 0
    allocated_size: int = 0
    real_size: int = 0
    initialised_size: int = 0
    data_runs: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        base = super().to_dict()
        base["resident"] = False
        base["starting_vcn"] = self.starting_vcn
        base["last_vcn"] = self.last_vcn
        base["allocated_size"] = self.allocated_size
        base["real_size"] = self.real_size
        base["data_runs"] = self.data_runs
        return base


@dataclass
class MFTRecord:
    header: MFTRecordHeader = field(default_factory=MFTRecordHeader)
    attributes: list[NTFSAttribute] = field(default_factory=list)
    standard_info: StandardInformation | None = None
    file_name: FileNameAttribute | None = None
    data_resident: bytes | None = None
    raw_data: bytes = b""
    resident: bool = True

    @property
    def name(self) -> str:
        return self.file_name.name if self.file_name else ""

    @property
    def is_directory(self) -> bool:
        return self.header.is_directory

    @property
    def is_deleted(self) -> bool:
        return self.header.is_deleted

    def to_dict(self) -> dict:
        return {
            "header": self.header.to_dict(),
            "name": self.name,
            "is_directory": self.is_directory,
            "is_deleted": self.is_deleted,
            "resident": self.resident,
            "file_size": self.file_name.real_size if self.file_name else 0,
            "standard_info": self.standard_info.to_dict() if self.standard_info else None,
            "file_name": self.file_name.to_dict() if self.file_name else None,
            "attributes": [a.to_dict() for a in self.attributes],
            "data_length": len(self.data_resident) if self.data_resident else 0,
        }


@dataclass
class RecoveredNTFSFile:
    name: str = ""
    original_name: str = ""
    deleted: bool = False
    is_directory: bool = False
    mft_record: int = 0
    file_size: int = 0
    data: bytes = b""
    sha256: str = ""
    created: str | None = None
    modified: str | None = None
    mft_modified: str | None = None
    accessed: str | None = None
    resident: bool = True
    recovery_status: str = "recovered"
    recovery_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.original_name,
            "mft_record": self.mft_record,
            "deleted": self.deleted,
            "resident": self.resident,
            "file_size": self.file_size,
            "sha256": self.sha256,
            "created": self.created,
            "modified": self.modified,
            "recovery_status": self.recovery_status,
        }
