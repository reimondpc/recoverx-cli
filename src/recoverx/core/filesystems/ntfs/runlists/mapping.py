from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DataRun:
    vcn_start: int = 0
    vcn_end: int = 0
    lcn: int = 0
    cluster_count: int = 0
    is_sparse: bool = False
    relative_offset: int = 0

    @property
    def is_resident(self) -> bool:
        return False

    @property
    def allocated(self) -> bool:
        return self.lcn >= 0 and not self.is_sparse

    @property
    def cluster_range(self) -> tuple[int, int]:
        return (self.lcn, self.lcn + self.cluster_count - 1)

    def to_dict(self) -> dict:
        return {
            "vcn_start": self.vcn_start,
            "vcn_end": self.vcn_end,
            "lcn": self.lcn,
            "cluster_count": self.cluster_count,
            "is_sparse": self.is_sparse,
            "relative_offset": self.relative_offset,
        }


def decode_runlist_entry(data: bytes, pos: int) -> tuple[DataRun | None, int]:
    if pos >= len(data):
        return None, pos
    header_byte = data[pos]
    if header_byte == 0:
        return None, pos
    count_bytes = header_byte & 0x0F
    offset_bytes = (header_byte >> 4) & 0x0F
    if pos + 1 + count_bytes + offset_bytes > len(data):
        return None, pos
    cluster_count = 0
    for i in range(count_bytes):
        cluster_count |= data[pos + 1 + i] << (8 * i)
    cluster_offset = 0
    if offset_bytes > 0:
        raw_offset = 0
        for i in range(offset_bytes):
            raw_offset |= data[pos + 1 + count_bytes + i] << (8 * i)
        if raw_offset & (1 << (offset_bytes * 8 - 1)):
            raw_offset |= -1 - (1 << (offset_bytes * 8)) + 1
        cluster_offset = raw_offset
    next_pos = pos + 1 + count_bytes + offset_bytes
    run = DataRun(
        cluster_count=cluster_count,
        lcn=cluster_offset,
        relative_offset=cluster_offset,
        is_sparse=(cluster_offset == 0 and offset_bytes == 0),
    )
    return run, next_pos


def resolve_runlist(runs: list[dict], bpb) -> list[DataRun]:
    resolved: list[DataRun] = []
    current_vcn: int = 0
    current_lcn: int = 0
    for raw_run in runs:
        cluster_count = raw_run["cluster_count"]
        cluster_offset = raw_run["cluster_offset"]
        is_sparse = raw_run.get("is_sparse", cluster_offset == 0)
        if is_sparse:
            dr = DataRun(
                vcn_start=current_vcn,
                vcn_end=current_vcn + cluster_count - 1,
                lcn=-1,
                cluster_count=cluster_count,
                is_sparse=True,
                relative_offset=0,
            )
            current_vcn += cluster_count
            resolved.append(dr)
            continue
        current_lcn += cluster_offset
        dr = DataRun(
            vcn_start=current_vcn,
            vcn_end=current_vcn + cluster_count - 1,
            lcn=current_lcn,
            cluster_count=cluster_count,
            is_sparse=False,
            relative_offset=cluster_offset,
        )
        current_vcn += cluster_count
        resolved.append(dr)
    return resolved


def vcn_to_lcn(vcn: int, resolved_runs: list[DataRun]) -> int:
    for run in resolved_runs:
        if run.vcn_start <= vcn <= run.vcn_end:
            if run.is_sparse:
                return -1
            offset = vcn - run.vcn_start
            return run.lcn + offset
    return -2


def runs_to_byte_offsets(runs: list[DataRun], bpb) -> list[dict]:
    cluster_size = bpb.cluster_size
    byte_runs: list[dict] = []
    for run in runs:
        if run.is_sparse:
            byte_runs.append({
                "byte_offset": -1,
                "byte_length": run.cluster_count * cluster_size,
                "is_sparse": True,
                "vcn_start": run.vcn_start,
                "vcn_end": run.vcn_end,
            })
        else:
            byte_offset = run.lcn * cluster_size
            byte_runs.append({
                "byte_offset": byte_offset,
                "byte_length": run.cluster_count * cluster_size,
                "is_sparse": False,
                "lcn": run.lcn,
                "vcn_start": run.vcn_start,
                "vcn_end": run.vcn_end,
            })
    return byte_runs
