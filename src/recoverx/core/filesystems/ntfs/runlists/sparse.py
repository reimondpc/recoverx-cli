from __future__ import annotations

from .mapping import DataRun


def is_sparse_runlist(data_runs: list[dict]) -> bool:
    for run in data_runs:
        if run.get("is_sparse", run.get("cluster_offset") == 0):
            return True
    return False


def count_sparse_regions(runs: list[DataRun]) -> int:
    return sum(1 for r in runs if r.is_sparse)


def count_allocated_regions(runs: list[DataRun]) -> int:
    return sum(1 for r in runs if not r.is_sparse)


def sparse_fill_size(runs: list[DataRun]) -> int:
    return sum(r.cluster_count for r in runs if r.is_sparse)


def allocated_cluster_count(runs: list[DataRun]) -> int:
    return sum(r.cluster_count for r in runs if not r.is_sparse)


class SparseHandler:
    def __init__(self, cluster_size: int) -> None:
        self.cluster_size = cluster_size

    def is_sparse(self, data_runs: list[dict]) -> bool:
        return is_sparse_runlist(data_runs)

    def compute_virtual_size(self, resolved_runs: list[DataRun]) -> int:
        if not resolved_runs:
            return 0
        return (resolved_runs[-1].vcn_end + 1) * self.cluster_size

    def compute_allocated_size(self, resolved_runs: list[DataRun]) -> int:
        return sum(r.cluster_count * self.cluster_size for r in resolved_runs if not r.is_sparse)

    def has_sparse_regions(self, resolved_runs: list[DataRun]) -> bool:
        return any(r.is_sparse for r in resolved_runs)

    def sparse_ratio(self, resolved_runs: list[DataRun]) -> float:
        if not resolved_runs:
            return 0.0
        total = sum(r.cluster_count for r in resolved_runs)
        if total == 0:
            return 0.0
        sparse_clusters = sum(r.cluster_count for r in resolved_runs if r.is_sparse)
        return sparse_clusters / total

    def describe(self, resolved_runs: list[DataRun]) -> dict:
        total = sum(r.cluster_count for r in resolved_runs)
        sparse_count = sum(r.cluster_count for r in resolved_runs if r.is_sparse)
        alloc_count = total - sparse_count
        return {
            "total_clusters": total,
            "allocated_clusters": alloc_count,
            "sparse_clusters": sparse_count,
            "sparse_ratio": sparse_count / total if total > 0 else 0.0,
            "virtual_size": self.compute_virtual_size(resolved_runs),
            "allocated_size": self.compute_allocated_size(resolved_runs),
        }
