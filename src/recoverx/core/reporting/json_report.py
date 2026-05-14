from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from recoverx import __version__
from recoverx.core.benchmark.advanced_benchmark import BenchmarkResult
from recoverx.core.carving.base import CarvedFile


class JSONReport:
    def __init__(self, output_path: str) -> None:
        self.output_path = output_path
        self.files: list[dict] = []
        self.benchmark: dict | None = None
        self.scan_info: dict = {}

    def add_file(self, carved: CarvedFile, sha256: str, saved_path: str) -> None:
        self.files.append(
            {
                "type": carved.signature_name.lower(),
                "extension": carved.extension,
                "offset": carved.offset_start,
                "offset_end": carved.offset_end,
                "size": len(carved.data),
                "sha256": sha256,
                "path": saved_path,
            }
        )

    def set_benchmark(self, bench: BenchmarkResult | dict) -> None:
        if isinstance(bench, BenchmarkResult):
            self.benchmark = bench.to_dict()
        else:
            self.benchmark = bench

    def set_scan_info(
        self,
        source: str,
        source_size: int,
        num_carvers: int,
        num_threads: int = 1,
        used_mmap: bool = False,
        filesystem: str | None = None,
    ) -> None:
        self.scan_info = {
            "tool": "RecoverX",
            "version": __version__,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "source_size": source_size,
            "num_carvers": num_carvers,
            "num_threads": num_threads,
            "used_mmap": used_mmap,
            "filesystem": filesystem,
        }

    def generate(self) -> dict:
        return {
            "scan_info": self.scan_info,
            "benchmark": self.benchmark or {},
            "files": self.files,
            "summary": {
                "total_files": len(self.files),
                "total_size": sum(f["size"] for f in self.files),
                "unique_hashes": len({f["sha256"] for f in self.files}),
            },
        }

    def write(self) -> str:
        data = self.generate()
        path = Path(self.output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))
        return str(path)
