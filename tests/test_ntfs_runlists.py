from __future__ import annotations

import os
import tempfile

from recoverx.core.filesystems.ntfs.runlists.mapping import (
    DataRun, resolve_runlist, vcn_to_lcn, runs_to_byte_offsets,
)
from recoverx.core.filesystems.ntfs.runlists.executor import RunlistExecutor
from recoverx.core.filesystems.ntfs.runlists.sparse import (
    SparseHandler, is_sparse_runlist, count_sparse_regions,
    count_allocated_regions,
)
from recoverx.core.filesystems.ntfs.runlists.validation import (
    validate_runlist, check_circular_runs,
)
from recoverx.core.filesystems.ntfs.structures import NTFSBootSector
from recoverx.core.utils.raw_reader import RawReader


def _make_bpb(cluster_size: int = 512) -> NTFSBootSector:
    return NTFSBootSector(
        bytes_per_sector=512,
        sectors_per_cluster=cluster_size // 512 if cluster_size >= 512 else 1,
        total_sectors=100000,
        mft_cluster=16,
        clusters_per_file_record=0xF6,
    )


def _make_reader(data: bytes) -> RawReader:
    f = tempfile.NamedTemporaryFile(delete=False)
    f.write(data)
    f.close()
    reader = RawReader(f.name)
    reader.open()
    return reader


class TestDataRun:
    def test_allocated_datarun(self):
        run = DataRun(vcn_start=0, vcn_end=9, lcn=100, cluster_count=10)
        assert run.allocated
        assert not run.is_sparse
        assert run.cluster_range == (100, 109)

    def test_sparse_datarun(self):
        run = DataRun(vcn_start=0, vcn_end=9, lcn=-1, cluster_count=10, is_sparse=True)
        assert not run.allocated
        assert run.is_sparse

    def test_to_dict(self):
        run = DataRun(vcn_start=0, vcn_end=4, lcn=50, cluster_count=5)
        d = run.to_dict()
        assert d["vcn_start"] == 0
        assert d["lcn"] == 50
        assert d["cluster_count"] == 5


class TestResolveRunlist:
    def test_resolve_single_run(self):
        runs = [{"cluster_count": 10, "cluster_offset": 100}]
        resolved = resolve_runlist(runs, None)
        assert len(resolved) == 1
        assert resolved[0].lcn == 100
        assert resolved[0].vcn_start == 0
        assert resolved[0].vcn_end == 9

    def test_resolve_relative_offsets(self):
        runs = [
            {"cluster_count": 5, "cluster_offset": 100},
            {"cluster_count": 5, "cluster_offset": 50},
        ]
        resolved = resolve_runlist(runs, None)
        assert len(resolved) == 2
        assert resolved[0].lcn == 100
        assert resolved[1].lcn == 150
        assert resolved[1].vcn_start == 5

    def test_resolve_sparse_run(self):
        runs = [
            {"cluster_count": 5, "cluster_offset": 100, "is_sparse": False},
            {"cluster_count": 5, "cluster_offset": 0, "is_sparse": True},
            {"cluster_count": 5, "cluster_offset": 50, "is_sparse": False},
        ]
        resolved = resolve_runlist(runs, None)
        assert len(resolved) == 3
        assert resolved[0].lcn == 100
        assert resolved[1].is_sparse
        assert resolved[1].lcn == -1
        assert resolved[2].lcn == 150
        assert resolved[2].vcn_start == 10

    def test_resolve_negative_offset(self):
        runs = [
            {"cluster_count": 10, "cluster_offset": 200},
            {"cluster_count": 5, "cluster_offset": -50},
        ]
        resolved = resolve_runlist(runs, None)
        assert len(resolved) == 2
        assert resolved[0].lcn == 200
        assert resolved[1].lcn == 150

    def test_vcn_to_lcn(self):
        runs = [{"cluster_count": 10, "cluster_offset": 100}]
        resolved = resolve_runlist(runs, None)
        assert vcn_to_lcn(0, resolved) == 100
        assert vcn_to_lcn(5, resolved) == 105
        assert vcn_to_lcn(9, resolved) == 109
        assert vcn_to_lcn(10, resolved) == -2

    def test_vcn_to_lcn_sparse(self):
        runs = [
            {"cluster_count": 5, "cluster_offset": 100},
            {"cluster_count": 5, "cluster_offset": 0, "is_sparse": True},
        ]
        resolved = resolve_runlist(runs, None)
        assert vcn_to_lcn(3, resolved) == 103
        assert vcn_to_lcn(7, resolved) == -1

    def test_runs_to_byte_offsets(self):
        bpb = _make_bpb(512)
        runs = [{"cluster_count": 10, "cluster_offset": 100}]
        resolved = resolve_runlist(runs, bpb)
        byte_runs = runs_to_byte_offsets(resolved, bpb)
        assert len(byte_runs) == 1
        assert byte_runs[0]["byte_offset"] == 100 * 512
        assert byte_runs[0]["byte_length"] == 10 * 512


class TestRunlistExecutor:
    def test_execute_simple(self):
        data = b"HELLO_NTFS_NON_RESIDENT_DATA!" * 100
        bpb = _make_bpb(512)
        reader = _make_reader(data)
        try:
            executor = RunlistExecutor(reader, bpb)
            runs = [{"cluster_count": 10, "cluster_offset": 0, "is_sparse": False}]
            result = executor.execute(runs, 200)
            assert len(result) == 200
            assert result == data[:200]
        finally:
            reader.close()
            os.unlink(reader.path)

    def test_execute_multiple_runs(self):
        chunk1 = b"AAAA" * 128
        chunk2 = b"BBBB" * 128
        chunk3 = b"CCCC" * 128
        data = chunk1 + chunk2 + chunk3
        bpb = _make_bpb(512)
        reader = _make_reader(data)
        try:
            executor = RunlistExecutor(reader, bpb)
            runs = [
                {"cluster_count": 1, "cluster_offset": 0, "is_sparse": False},
                {"cluster_count": 1, "cluster_offset": 1, "is_sparse": False},
                {"cluster_count": 1, "cluster_offset": 1, "is_sparse": False},
            ]
            result = executor.execute(runs, 512 * 3)
            assert len(result) == 512 * 3
            assert result[:512] == chunk1[:512]
            assert result[512:1024] == chunk2[:512]
            assert result[1024:1536] == chunk3[:512]
        finally:
            reader.close()
            os.unlink(reader.path)

    def test_execute_max_bytes(self):
        data = b"X" * 4096
        bpb = _make_bpb(512)
        reader = _make_reader(data)
        try:
            executor = RunlistExecutor(reader, bpb)
            runs = [{"cluster_count": 8, "cluster_offset": 0, "is_sparse": False}]
            result = executor.execute(runs, 4096, max_bytes=1024)
            assert len(result) == 1024
        finally:
            reader.close()
            os.unlink(reader.path)

    def test_execute_chunked(self):
        data = b"CHUNKED" * 512
        bpb = _make_bpb(512)
        reader = _make_reader(data)
        try:
            executor = RunlistExecutor(reader, bpb)
            runs = [{"cluster_count": 4, "cluster_offset": 0, "is_sparse": False}]
            chunks = list(executor.execute_chunked(runs, 2048, chunk_size=512))
            total = sum(len(c) for c in chunks)
            assert total == 2048
        finally:
            reader.close()
            os.unlink(reader.path)

    def test_read_cluster(self):
        data = b"A" * 512
        bpb = _make_bpb(512)
        reader = _make_reader(data)
        try:
            executor = RunlistExecutor(reader, bpb)
            cluster = executor.read_cluster(0)
            assert len(cluster) == 512
        finally:
            reader.close()
            os.unlink(reader.path)

    def test_read_clusters(self):
        data = b"B" * (512 * 3)
        bpb = _make_bpb(512)
        reader = _make_reader(data)
        try:
            executor = RunlistExecutor(reader, bpb)
            clusters = executor.read_clusters(0, 3)
            assert len(clusters) == 512 * 3
        finally:
            reader.close()
            os.unlink(reader.path)

    def test_estimate_recoverable(self):
        data = b"X" * 5120
        bpb = _make_bpb(512)
        reader = _make_reader(data)
        try:
            executor = RunlistExecutor(reader, bpb)
            runs = [{"cluster_count": 10, "cluster_offset": 0}]
            total, rec, lost = executor.estimate_recoverable_bytes(
                resolve_runlist(runs, bpb), 5120
            )
            assert total == 5120
            assert rec == 5120
            assert lost == 0
        finally:
            reader.close()
            os.unlink(reader.path)

    def test_estimate_recoverable_partial(self):
        data = b"X" * 512
        bpb = _make_bpb(512)
        reader = _make_reader(data)
        try:
            executor = RunlistExecutor(reader, bpb)
            runs = [{"cluster_count": 10, "cluster_offset": 0}]
            total, rec, lost = executor.estimate_recoverable_bytes(
                resolve_runlist(runs, bpb), 5120
            )
            assert total == 5120
            assert rec == 512
            assert lost > 0
        finally:
            reader.close()
            os.unlink(reader.path)

    def test_execute_sparse_aware(self):
        data = b"X" * (2 * 512) + b"Y" * (2 * 512)
        bpb = _make_bpb(512)
        reader = _make_reader(data)
        try:
            executor = RunlistExecutor(reader, bpb)
            runs = [
                {"cluster_count": 2, "cluster_offset": 0, "is_sparse": False},
                {"cluster_count": 3, "cluster_offset": 0, "is_sparse": True},
                {"cluster_count": 2, "cluster_offset": 2, "is_sparse": False},
            ]
            result = executor.execute_sparse_aware(runs, 7 * 512)
            assert len(result) == 7 * 512
            assert result[:1024] == data[:1024]
            assert result[1024:2560] == b"\x00" * 1536
            assert result[2560:] == data[1024:]
        finally:
            reader.close()
            os.unlink(reader.path)

    def test_read_vcn_range(self):
        data = b"VCN_RANGE" * 569
        bpb = _make_bpb(512)
        reader = _make_reader(data)
        try:
            executor = RunlistExecutor(reader, bpb)
            runs = [{"cluster_count": 10, "cluster_offset": 0}]
            resolved = resolve_runlist(runs, bpb)
            result = executor.read_vcn_range(resolved, 2, 5)
            assert len(result) == 4 * 512
        finally:
            reader.close()
            os.unlink(reader.path)


class TestSparseHandler:
    def test_is_sparse_runlist(self):
        non_sparse = {"cluster_count": 5, "cluster_offset": 100, "is_sparse": False}
        sparse = {"cluster_count": 5, "cluster_offset": 0, "is_sparse": True}
        zero_off = {"cluster_count": 5, "cluster_offset": 0, "is_sparse": False}
        assert not is_sparse_runlist([non_sparse])
        assert is_sparse_runlist([sparse])
        assert not is_sparse_runlist([zero_off])
        assert is_sparse_runlist([
            {"cluster_count": 5, "cluster_offset": 100, "is_sparse": False},
            {"cluster_count": 5, "cluster_offset": 0, "is_sparse": True},
        ])

    def test_count_sparse_regions(self):
        runs = [
            DataRun(vcn_start=0, vcn_end=4, lcn=100, cluster_count=5, is_sparse=False),
            DataRun(vcn_start=5, vcn_end=9, lcn=-1, cluster_count=5, is_sparse=True),
        ]
        assert count_sparse_regions(runs) == 1
        assert count_allocated_regions(runs) == 1

    def test_sparse_handler(self):
        handler = SparseHandler(512)
        runs = [
            DataRun(vcn_start=0, vcn_end=4, lcn=100, cluster_count=5, is_sparse=False),
            DataRun(vcn_start=5, vcn_end=14, lcn=-1, cluster_count=10, is_sparse=True),
        ]
        assert handler.has_sparse_regions(runs)
        assert handler.compute_virtual_size(runs) == 15 * 512
        assert handler.compute_allocated_size(runs) == 5 * 512
        ratio = handler.sparse_ratio(runs)
        assert ratio == 10 / 15

    def test_describe(self):
        handler = SparseHandler(512)
        runs = [
            DataRun(vcn_start=0, vcn_end=4, lcn=100, cluster_count=5, is_sparse=False),
            DataRun(vcn_start=5, vcn_end=9, lcn=-1, cluster_count=5, is_sparse=True),
        ]
        desc = handler.describe(runs)
        assert desc["total_clusters"] == 10
        assert desc["allocated_clusters"] == 5
        assert desc["sparse_clusters"] == 5


class TestRunlistValidation:
    def test_empty_runlist(self):
        issues = validate_runlist([], 0)
        assert len(issues) == 1
        assert issues[0].code == "EMPTY_RUNLIST"

    def test_valid_runlist(self):
        runs = [DataRun(vcn_start=0, vcn_end=9, lcn=100, cluster_count=10)]
        issues = validate_runlist(runs, 10)
        assert len(issues) == 0

    def test_vcn_overlap(self):
        runs = [
            DataRun(vcn_start=0, vcn_end=4, lcn=100, cluster_count=5),
            DataRun(vcn_start=3, vcn_end=7, lcn=200, cluster_count=5),
        ]
        issues = validate_runlist(runs, 10)
        overlap_issues = [i for i in issues if i.code == "VCN_OVERLAP"]
        assert len(overlap_issues) == 1

    def test_invalid_lcn(self):
        runs = [DataRun(vcn_start=0, vcn_end=4, lcn=-5, cluster_count=5)]
        issues = validate_runlist(runs, 5)
        lcn_issues = [i for i in issues if i.code == "INVALID_LCN"]
        assert len(lcn_issues) == 1

    def test_lcn_out_of_bounds(self):
        runs = [
            DataRun(vcn_start=0, vcn_end=4, lcn=999999, cluster_count=5),
        ]
        issues = validate_runlist(runs, 5, volume_clusters=100)
        oob_issues = [i for i in issues if i.code == "LCN_OUT_OF_BOUNDS"]
        assert len(oob_issues) == 1

    def test_impossible_size(self):
        runs = [
            DataRun(vcn_start=0, vcn_end=1999999, lcn=100, cluster_count=2000000),
        ]
        issues = validate_runlist(runs, 2000000)
        size_issues = [i for i in issues if i.code == "IMPOSSIBLE_SIZE"]
        assert len(size_issues) == 1

    def test_lcn_overlap(self):
        runs = [
            DataRun(vcn_start=0, vcn_end=4, lcn=100, cluster_count=5),
            DataRun(vcn_start=5, vcn_end=9, lcn=102, cluster_count=5),
        ]
        issues = validate_runlist(runs, 10)
        overlap_issues = [i for i in issues if i.code == "LCN_OVERLAP"]
        assert len(overlap_issues) == 1

    def test_vcn_exceeds_total(self):
        runs = [DataRun(vcn_start=0, vcn_end=19, lcn=100, cluster_count=20)]
        issues = validate_runlist(runs, 10)
        vcn_issues = [i for i in issues if i.code == "VCN_EXCEEDS_TOTAL"]
        assert len(vcn_issues) == 1

    def test_zero_cluster_count(self):
        runs = [DataRun(vcn_start=0, vcn_end=-1, lcn=100, cluster_count=0)]
        issues = validate_runlist(runs, 0)
        zero_issues = [i for i in issues if i.code == "ZERO_CLUSTER_COUNT"]
        assert len(zero_issues) == 1


class TestCircularRunDetection:
    def test_no_circular(self):
        runs = [
            DataRun(vcn_start=0, vcn_end=4, lcn=100, cluster_count=5),
            DataRun(vcn_start=5, vcn_end=9, lcn=200, cluster_count=5),
        ]
        issues = check_circular_runs(runs)
        assert len(issues) == 0

    def test_circular_detected(self):
        runs = [
            DataRun(vcn_start=0, vcn_end=4, lcn=100, cluster_count=5),
            DataRun(vcn_start=5, vcn_end=9, lcn=100, cluster_count=3),
        ]
        issues = check_circular_runs(runs)
        circular = [i for i in issues if i.code == "CIRCULAR_RUN"]
        assert len(circular) >= 1

    def test_sparse_ignored(self):
        runs = [
            DataRun(vcn_start=0, vcn_end=4, lcn=100, cluster_count=5),
            DataRun(vcn_start=5, vcn_end=9, lcn=-1, cluster_count=5, is_sparse=True),
            DataRun(vcn_start=10, vcn_end=14, lcn=100, cluster_count=5),
        ]
        issues = check_circular_runs(runs)
        circular = [i for i in issues if i.code == "CIRCULAR_RUN"]
        assert len(circular) >= 1
