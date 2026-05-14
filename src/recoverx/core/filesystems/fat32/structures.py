from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FAT32BootSector:
    bytes_per_sector: int = 512
    sectors_per_cluster: int = 1
    reserved_sectors: int = 32
    fat_count: int = 2
    fat_size_sectors: int = 0
    root_cluster: int = 2
    total_sectors: int = 0
    fs_info_sector: int = 1
    backup_boot_sector: int = 6
    media_descriptor: int = 0xF8
    volume_id: str = ""
    volume_label: str = ""
    oem_id: str = ""
    active_fat: int = 0
    mirrroring_enabled: bool = True
    fs_version: int = 0
    signature_valid: bool = False
    hidden_sectors: int = 0
    boot_sector_copy_count: int = 1

    @property
    def cluster_size(self) -> int:
        return self.bytes_per_sector * self.sectors_per_cluster

    @property
    def fat_start(self) -> int:
        return self.reserved_sectors * self.bytes_per_sector

    @property
    def data_start(self) -> int:
        return (
            self.reserved_sectors + self.fat_count * self.fat_size_sectors
        ) * self.bytes_per_sector

    @property
    def total_clusters(self) -> int:
        data_sectors = self.total_sectors - (
            self.reserved_sectors + self.fat_count * self.fat_size_sectors
        )
        return data_sectors // self.sectors_per_cluster

    def to_dict(self) -> dict:
        return {
            "bytes_per_sector": self.bytes_per_sector,
            "sectors_per_cluster": self.sectors_per_cluster,
            "cluster_size": self.cluster_size,
            "reserved_sectors": self.reserved_sectors,
            "fat_count": self.fat_count,
            "fat_size_sectors": self.fat_size_sectors,
            "fat_start_offset": self.fat_start,
            "data_start_offset": self.data_start,
            "root_cluster": self.root_cluster,
            "total_sectors": self.total_sectors,
            "total_clusters": self.total_clusters,
            "volume_label": self.volume_label,
            "volume_id": self.volume_id,
            "oem_id": self.oem_id,
            "signature_valid": self.signature_valid,
            "media_descriptor": f"0x{self.media_descriptor:02X}",
        }


@dataclass
class FATTimestamp:
    year: int = 0
    month: int = 0
    day: int = 0
    hour: int = 0
    minute: int = 0
    second: int = 0

    def to_datetime(self) -> datetime | None:
        try:
            if self.year == 0:
                return None
            return datetime(self.year, self.month, self.day, self.hour, self.minute, self.second)
        except (ValueError, OverflowError):
            return None

    def to_dict(self) -> dict:
        return {
            "year": self.year,
            "month": self.month,
            "day": self.day,
            "hour": self.hour,
            "minute": self.minute,
            "second": self.second,
            "iso": self.to_datetime().isoformat() if self.to_datetime() else None,
        }


@dataclass
class FATAttributes:
    read_only: bool = False
    hidden: bool = False
    system: bool = False
    volume_label: bool = False
    subdirectory: bool = False
    archive: bool = False
    device: bool = False

    @property
    def byte(self) -> int:
        val = 0
        if self.read_only:
            val |= 0x01
        if self.hidden:
            val |= 0x02
        if self.system:
            val |= 0x04
        if self.volume_label:
            val |= 0x08
        if self.subdirectory:
            val |= 0x10
        if self.archive:
            val |= 0x20
        if self.device:
            val |= 0x40
        return val

    def to_dict(self) -> dict:
        return {
            "read_only": self.read_only,
            "hidden": self.hidden,
            "system": self.system,
            "volume_label": self.volume_label,
            "subdirectory": self.subdirectory,
            "archive": self.archive,
        }

    def __str__(self) -> str:
        parts = []
        if self.read_only:
            parts.append("R")
        if self.hidden:
            parts.append("H")
        if self.system:
            parts.append("S")
        if self.volume_label:
            parts.append("L")
        if self.subdirectory:
            parts.append("D")
        if self.archive:
            parts.append("A")
        return "".join(parts) if parts else "---"


@dataclass
class FATDirEntry:
    name: str = ""
    extension: str = ""
    short_name: str = ""
    long_name: str = ""
    attributes: FATAttributes = field(default_factory=FATAttributes)
    deleted: bool = False
    is_directory: bool = False
    is_volume_label: bool = False
    start_cluster: int = 0
    file_size: int = 0
    created: FATTimestamp = field(default_factory=FATTimestamp)
    last_accessed: FATTimestamp = field(default_factory=FATTimestamp)
    last_modified: FATTimestamp = field(default_factory=FATTimestamp)
    offset_in_image: int = 0
    original_raw: bytes = b""

    def full_name(self) -> str:
        return self.long_name or self.short_name

    def to_dict(self) -> dict:
        return {
            "short_name": self.short_name,
            "long_name": self.long_name,
            "extension": self.extension,
            "deleted": self.deleted,
            "is_directory": self.is_directory,
            "is_volume_label": self.is_volume_label,
            "attributes": self.attributes.to_dict(),
            "attributes_str": str(self.attributes),
            "start_cluster": self.start_cluster,
            "file_size": self.file_size,
            "created": self.created.to_dict(),
            "last_modified": self.last_modified.to_dict(),
            "last_accessed": self.last_accessed.to_dict(),
            "offset_in_image": self.offset_in_image,
        }


@dataclass
class RecoveredFile:
    name: str = ""
    extension: str = ""
    original_name: str = ""
    deleted: bool = False
    is_directory: bool = False
    start_cluster: int = 0
    cluster_chain: list[int] = field(default_factory=list)
    file_size: int = 0
    data: bytes = b""
    sha256: str = ""
    created: FATTimestamp = field(default_factory=FATTimestamp)
    last_modified: FATTimestamp = field(default_factory=FATTimestamp)
    last_accessed: FATTimestamp = field(default_factory=FATTimestamp)
    attributes: FATAttributes = field(default_factory=FATAttributes)
    recovery_status: str = "recovered"
    recovery_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.original_name,
            "extension": self.extension,
            "deleted": self.deleted,
            "start_cluster": self.start_cluster,
            "cluster_chain": self.cluster_chain,
            "file_size": self.file_size,
            "sha256": self.sha256,
            "created": self.created.to_dict(),
            "last_modified": self.last_modified.to_dict(),
            "last_accessed": self.last_accessed.to_dict(),
            "attributes": self.attributes.to_dict(),
            "recovery_status": self.recovery_status,
        }
