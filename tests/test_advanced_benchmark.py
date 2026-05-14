from __future__ import annotations

import time

from recoverx.core.benchmark.advanced_benchmark import AdvancedBenchmark, BenchmarkResult


class TestAdvancedBenchmark:
    def test_start_stop(self):
        bench = AdvancedBenchmark()
        bench.start()
        time.sleep(0.01)
        bench.stop()
        assert bench.elapsed > 0

    def test_speed_mbps(self):
        bench = AdvancedBenchmark()
        bench.start()
        bench.bytes_scanned = 10 * 1024 * 1024
        bench.stop()
        assert bench.speed_mbps > 0

    def test_files_per_minute(self):
        bench = AdvancedBenchmark()
        bench.start()
        bench.files_found = 60
        bench.stop()
        assert bench.files_per_minute > 0

    def test_result_object(self):
        bench = AdvancedBenchmark()
        bench.start()
        bench.bytes_scanned = 1024 * 1024
        bench.files_found = 5
        bench.num_threads = 2
        bench.used_mmap = True
        bench.scanner_type = "mmap"
        bench.stop()
        r = bench.result()
        assert isinstance(r, BenchmarkResult)
        assert r.bytes_scanned == 1024 * 1024
        assert r.files_found == 5
        assert r.num_threads == 2
        assert r.used_mmap
        assert r.scanner_type == "mmap"

    def test_result_to_dict(self):
        r = BenchmarkResult(
            elapsed_seconds=1.5,
            speed_mbps=50.0,
            bytes_scanned=1024,
            files_found=3,
            files_per_minute=120.0,
            cpu_percent=25.0,
            peak_rss_mb=100.0,
            num_threads=4,
            per_thread_seconds=[1.0, 1.1, 1.2, 1.3],
            used_mmap=True,
            scanner_type="mmap",
        )
        d = r.to_dict()
        assert d["elapsed_seconds"] == 1.5
        assert d["num_threads"] == 4
        assert d["used_mmap"] is True

    def test_summary_contains_info(self):
        r = BenchmarkResult(
            elapsed_seconds=2.0,
            speed_mbps=100.0,
            bytes_scanned=256 * 1024 * 1024,
            files_found=10,
            files_per_minute=300.0,
            cpu_percent=50.0,
            peak_rss_mb=200.0,
        )
        s = r.summary()
        assert "2.00s" in s
        assert "100.0" in s
        assert "10" in s
