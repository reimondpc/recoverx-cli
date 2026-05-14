from __future__ import annotations

import logging
from pathlib import Path

from recoverx.core.utils.hashing import sha256
from recoverx.core.utils.raw_reader import RawReader

from .directory import parse_directory_entries, read_cluster_chain, read_cluster_data
from .structures import FAT32BootSector, FATDirEntry, RecoveredFile

logger = logging.getLogger("recoverx")


class FAT32Recovery:
    def __init__(self, reader: RawReader, bpb: FAT32BootSector) -> None:
        self.reader = reader
        self.bpb = bpb

    def find_deleted_entries(
        self,
        cluster: int | None = None,
        max_clusters: int = 0,
    ) -> list[FATDirEntry]:
        start = cluster if cluster is not None else self.bpb.root_cluster
        chain, status = read_cluster_chain(self.reader, self.bpb, start, max_clusters)
        if not chain:
            logger.warning("Cannot read directory cluster chain: %s", status)
            return []

        data = bytearray()
        for c in chain:
            data.extend(read_cluster_data(self.reader, self.bpb, c))

        all_entries = parse_directory_entries(bytes(data))
        return [e for e in all_entries if e.deleted and not e.is_directory]

    def recover_deleted_file(self, entry: FATDirEntry) -> RecoveredFile:
        recovered = RecoveredFile(
            name=entry.short_name,
            extension=entry.extension,
            original_name=entry.full_name(),
            deleted=True,
            is_directory=entry.is_directory,
            start_cluster=entry.start_cluster,
            file_size=entry.file_size,
            created=entry.created,
            last_modified=entry.last_modified,
            last_accessed=entry.last_accessed,
            attributes=entry.attributes,
        )

        if entry.is_directory:
            recovered.recovery_status = "skipped_directory"
            return recovered

        if entry.start_cluster < 2:
            recovered.recovery_status = "no_start_cluster"
            recovered.recovery_notes.append(f"Invalid start cluster: {entry.start_cluster}")
            return recovered

        chain, status = read_cluster_chain(self.reader, self.bpb, entry.start_cluster)
        recovered.cluster_chain = chain

        if not chain:
            recovered.recovery_status = "empty_chain"
            recovered.recovery_notes.append(f"Cluster chain empty: {status}")
            return recovered

        data = bytearray()
        for cluster in chain:
            cluster_data = read_cluster_data(self.reader, self.bpb, cluster)
            data.extend(cluster_data)

        if entry.file_size > 0 and len(data) > entry.file_size:
            data = data[: entry.file_size]
        elif entry.file_size == 0 and data:
            recovered.recovery_notes.append("file_size was 0 but data found, using chain size")

        recovered.data = bytes(data)
        recovered.sha256 = sha256(recovered.data)

        if recovered.file_size > 0 and len(recovered.data) < recovered.file_size:
            recovered.recovery_notes.append(
                f"truncated: expected {recovered.file_size} B, recovered {len(recovered.data)} B"
            )
            recovered.recovery_status = "truncated"
        else:
            recovered.recovery_status = "recovered"

        return recovered

    def save_recovered(
        self,
        recovered: RecoveredFile,
        output_dir: str = "recovered",
    ) -> str:
        out = Path(output_dir) / "fat32_recovery"
        out.mkdir(parents=True, exist_ok=True)

        base_name = recovered.original_name or f"cluster_{recovered.start_cluster}"
        safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in base_name)

        if recovered.deleted:
            safe_name = f"DELETED_{safe_name}"

        if not safe_name:
            safe_name = f"recovered_cluster_{recovered.start_cluster}"

        ext = f".{recovered.extension}" if recovered.extension else ""
        if ext and not safe_name.endswith(ext):
            safe_name += ext

        filepath = out / safe_name
        filepath.write_bytes(recovered.data)
        return str(filepath)
