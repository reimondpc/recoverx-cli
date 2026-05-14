from __future__ import annotations

import json
import tempfile
from pathlib import Path

from recoverx.core.benchmark.advanced_benchmark import BenchmarkResult
from recoverx.core.carving.base import CarvedFile
from recoverx.core.reporting.json_report import JSONReport


class TestJSONReport:
    def test_add_file(self):
        report = JSONReport("/tmp/test_report.json")
        cf = CarvedFile(
            data=b"test", offset_start=100, offset_end=200, signature_name="JPEG", extension="jpg"
        )
        report.add_file(cf, "abc123", "recovered/jpg_001.jpg")
        assert len(report.files) == 1
        assert report.files[0]["sha256"] == "abc123"

    def test_set_benchmark(self):
        report = JSONReport("/tmp/test_report.json")
        br = BenchmarkResult(elapsed_seconds=1.5, speed_mbps=50.0)
        report.set_benchmark(br)
        assert report.benchmark["elapsed_seconds"] == 1.5

    def test_set_scan_info(self):
        report = JSONReport("/tmp/test_report.json")
        report.set_scan_info(
            source="test.img", source_size=1024, num_carvers=3, num_threads=2, used_mmap=True
        )
        assert report.scan_info["source"] == "test.img"
        assert report.scan_info["version"] is not None

    def test_generate_structure(self):
        report = JSONReport("/tmp/test_report.json")
        report.set_scan_info(source="test.img", source_size=1024, num_carvers=3)
        cf = CarvedFile(
            data=b"data", offset_start=100, offset_end=200, signature_name="PNG", extension="png"
        )
        report.add_file(cf, "def456", "recovered/png_001.png")
        data = report.generate()
        assert "scan_info" in data
        assert "files" in data
        assert "summary" in data
        assert data["summary"]["total_files"] == 1

    def test_write_to_file(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            fname = f.name
        report = JSONReport(fname)
        report.set_scan_info(source="test.img", source_size=512, num_carvers=2)
        report.write()
        content = Path(fname).read_text()
        parsed = json.loads(content)
        assert parsed["scan_info"]["source"] == "test.img"
