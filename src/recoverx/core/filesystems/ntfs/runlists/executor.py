from __future__ import annotations

import logging

from recoverx.core.utils.raw_reader import RawReader

from .mapping import DataRun, resolve_runlist

logger = logging.getLogger("recoverx")


class RunlistExecutor:
    def __init__(self, reader: RawReader, bpb) -> None:
        self.reader = reader
        self.bpb = bpb
        self.cluster_size: int = bpb.cluster_size

    def execute(
        self,
        data_runs: list[dict],
        real_size: int,
        initialised_size: int = 0,
        max_bytes: int = 0,
    ) -> bytes:
        resolved = resolve_runlist(data_runs, self.bpb)
        return self._read_resolved(resolved, real_size, max_bytes)

    def execute_chunked(
        self,
        data_runs: list[dict],
        real_size: int,
        chunk_size: int = 65536,
    ):
        resolved = resolve_runlist(data_runs, self.bpb)
        return self._read_chunked(resolved, real_size, chunk_size)

    def execute_sparse_aware(
        self,
        data_runs: list[dict],
        real_size: int,
        initialised_size: int = 0,
        max_bytes: int = 0,
    ) -> bytes:
        resolved = resolve_runlist(data_runs, self.bpb)
        return self._read_resolved_sparse(resolved, real_size, max_bytes)

    def read_vcn_range(
        self, resolved: list[DataRun], start_vcn: int, end_vcn: int
    ) -> bytes:
        cluster_size = self.cluster_size
        data = bytearray()
        for run in resolved:
            if run.vcn_end < start_vcn:
                continue
            if run.vcn_start > end_vcn:
                break
            read_start = max(run.vcn_start, start_vcn)
            read_end = min(run.vcn_end, end_vcn)
            count = read_end - read_start + 1
            if run.is_sparse:
                data.extend(b"\x00" * (count * cluster_size))
            else:
                offset = read_start - run.vcn_start
                byte_offset = (run.lcn + offset) * cluster_size
                chunk = self.reader.read_at(byte_offset, count * cluster_size)
                data.extend(chunk)
        return bytes(data)

    def read_cluster(self, lcn: int) -> bytes:
        offset = lcn * self.cluster_size
        return self.reader.read_at(offset, self.cluster_size)

    def read_clusters(self, start_lcn: int, count: int) -> bytes:
        offset = start_lcn * self.cluster_size
        size = count * self.cluster_size
        return self.reader.read_at(offset, size)

    def byte_offset_from_lcn(self, lcn: int) -> int:
        return lcn * self.cluster_size

    def _read_resolved(
        self, resolved: list[DataRun], real_size: int, max_bytes: int = 0,
    ) -> bytes:
        cluster_size = self.cluster_size
        limit = max_bytes if max_bytes > 0 else real_size
        data = bytearray()
        remaining = limit
        for run in resolved:
            if remaining <= 0:
                break
            if run.is_sparse:
                fill = min(run.cluster_count * cluster_size, remaining)
                data.extend(b"\x00" * fill)
                remaining -= fill
            else:
                byte_offset = run.lcn * cluster_size
                to_read = min(run.cluster_count * cluster_size, remaining)
                chunk = self.reader.read_at(byte_offset, to_read)
                data.extend(chunk)
                remaining -= len(chunk)
        return bytes(data[:real_size])

    def _read_chunked(self, resolved: list[DataRun], real_size: int, chunk_size: int):
        cluster_size = self.cluster_size
        remaining = real_size
        for run in resolved:
            if remaining <= 0:
                break
            if run.is_sparse:
                fill = min(run.cluster_count * cluster_size, remaining)
                remaining -= fill
                yield b"\x00" * fill
            else:
                byte_offset = run.lcn * cluster_size
                run_bytes = min(run.cluster_count * cluster_size, remaining)
                pos = 0
                while pos < run_bytes:
                    to_read = min(chunk_size, run_bytes - pos)
                    chunk = self.reader.read_at(byte_offset + pos, to_read)
                    yield chunk
                    pos += len(chunk)
                remaining -= run_bytes

    def _read_resolved_sparse(
        self, resolved: list[DataRun], real_size: int, max_bytes: int = 0,
    ) -> bytes:
        cluster_size = self.cluster_size
        limit = max_bytes if max_bytes > 0 else real_size
        data = bytearray()
        remaining = limit
        for run in resolved:
            if remaining <= 0:
                break
            run_bytes = run.cluster_count * cluster_size
            if run.is_sparse:
                fill = min(run_bytes, remaining)
                data.extend(b"\x00" * fill)
                remaining -= fill
            elif run.lcn >= 0:
                byte_offset = run.lcn * cluster_size
                if byte_offset + run_bytes > self.reader.size:
                    actual = max(0, self.reader.size - byte_offset)
                    to_read = min(actual, remaining)
                    chunk = self.reader.read_at(byte_offset, to_read)
                    data.extend(chunk)
                    remaining -= len(chunk)
                else:
                    to_read = min(run_bytes, remaining)
                    chunk = self.reader.read_at(byte_offset, to_read)
                    data.extend(chunk)
                    remaining -= len(chunk)
        return bytes(data[:real_size])

    def estimate_recoverable_bytes(
        self, resolved: list[DataRun], real_size: int,
    ) -> tuple[int, int, int]:
        total = 0
        recoverable = 0
        lost = 0
        cluster_size = self.cluster_size
        for run in resolved:
            run_bytes = run.cluster_count * cluster_size
            total += run_bytes
            if run.is_sparse:
                recoverable += run_bytes
            elif run.lcn >= 0:
                byte_offset = run.lcn * cluster_size
                if byte_offset + run_bytes <= self.reader.size:
                    recoverable += run_bytes
                else:
                    partial = max(0, self.reader.size - byte_offset)
                    recoverable += partial
                    lost += run_bytes - partial
            else:
                lost += run_bytes
        actual_size = min(real_size, total)
        recoverable = min(recoverable, actual_size)
        return actual_size, recoverable, lost
