# Roadmap

RecoverX development roadmap organised by target version.  This is a living
document — priorities shift based on community feedback and real-world testing.

## Legend

| Symbol | Meaning |
|--------|---------|
| ✅     | Done    |
| 🔜     | Planned |
| 🔬     | Research phase |

---

## v0.2.0 — Initial Professional MVP ✅

- [x] JPEG carving (FFD8FF / FFD9)
- [x] RawReader for binary disk access
- [x] RecoveryManager with auto-increment naming
- [x] psutil-based disk detector
- [x] Typer CLI (`info`, `scan`)
- [x] Rich terminal output (progress bars, tables)
- [x] Dual logging (console + file)
- [x] BaseCarver abstract interface
- [x] Signature registry (`signatures.py`)
- [x] `src/` layout packaging
- [x] pytest test suite (23 tests)
- [x] black / isort / flake8 toolchain
- [x] MIT license
- [x] CHANGELOG.md

## v0.3.0 — Additional Carvers ✅

- [x] **PNG carver** — signature `\x89PNG\r\n\x1a\n` / `IEND`
- [x] **SHA-256 hashing** — per-file hash with deduplication support
- [x] **Chunked streaming scanner** — process arbitrarily large images with bounded memory
- [x] **Sliding window overlap** — handle cross-boundary headers/footers
- [x] **Benchmark suite** — scan time, MB/s, and file count reporting

## v0.4.0 — Performance + Forensics ✅

- [x] **GIF carver** — GIF87a / GIF89a with 4 MB lookback
- [x] **BMP carver** — header-declared size extraction
- [x] **PDF carver** — `%PDF` / `%%EOF` with 8 MB lookback
- [x] **`mmap`-based scanner** — zero-copy reads, auto-fallback to streaming
- [x] **Multithreaded scanner** — parallel region scanning, `--threads` CLI flag
- [x] **Advanced benchmark** — CPU%, peak RSS, files/min, per-thread timing
- [x] **JSON forensic reports** — structured output, `--report report.json`
- [x] **Filesystem detection** — FAT12/16/32, exFAT, NTFS, ext2/3/4 superblock parsing
- [x] **Hash database** — persistent SHA-256 dedup across runs
- [x] **Direct disk access** — `recoverx devices`, `/dev/sdX` support
- [x] **111 tests** — black / isort / flake8 clean

## v0.5.0 — Recovery Intelligence ✅

- [x] **FAT32 boot sector parser** — BPB field parsing, validation (signatures, cluster sizes, geometry)
- [x] **FAT32 directory traversal** — SFN + LFN entries, deleted marker (0xE5), free marker (0x00), recursive subdirectory walking
- [x] **FAT cluster chain reader** — FAT32 FAT entry walking with loop/bad-cluster/free/zero detection
- [x] **FAT32 deleted file recovery** — scan for 0xE5 entries, reconstruct cluster chains, truncate to declared size, SHA-256
- [x] **FAT32 CLI** — `recoverx fat32 {info,list,deleted,recover}` with `--json` output
- [x] **Test image generator** — reproducible FAT32 images with normal/deleted files and subdirectories
- [x] **187 tests** — black / isort / flake8 clean

## v0.5.5 — Hardening, QA & Automation ✅

- [x] **GitHub Actions CI/CD** — matrix testing (3.10/3.11/3.12), linting, type checking, security scanning
- [x] **Test coverage** — `pytest-cov` with 81% overall coverage, terminal/XML/HTML reporting
- [x] **Fuzz testing** — 21 fuzz tests for FAT32 boot sectors, directories, FAT chains, memory safety
- [x] **Stress datasets** — fragmented images, deep directories, partial overwrites, FAT loops, orphans
- [x] **Recovery validation** — precision, recovery rate, metadata integrity, hash consistency
- [x] **Advanced logging** — FORENSIC level (15), thread IDs, configurable console/file levels
- [x] **Performance profiler** — `Profiler` context manager with CPU/RAM/throughput, JSON export
- [x] **Architecture registries** — scanner, filesystem, carver, report registries for plugin loading
- [x] **Static analysis** — `mypy` type checking (45 files, 0 errors) + `bandit` security scan (0 issues)
- [x] **Packaging** — wheel + sdist verified, `build` + `twine` in dev deps
- [x] **216 tests** — flake8 / mypy / bandit clean

## v0.6.0 — Filesystem Awareness ✅

- [ ] **MBR / GPT partition table parser**
- [x] **FAT32 reader** — cluster chains, directory entries, long file names
- [ ] **exFAT reader**
- [x] **NTFS reader** — `$MFT`, attributes, resident data, deleted entry detection
- [ ] **ext2/3/4 reader**
- [ ] **Unallocated space extraction** — carve only gaps between allocated files
- [ ] **File system metadata reporting** — timestamps, permissions, paths

## v0.6.5 — Non-Resident & Fragmented NTFS Recovery ✅

- [x] **Runlist execution engine** — `DataRun` dataclass, `resolve_runlist()` VCN→LCN translation, `runs_to_byte_offsets()`
- [x] **RunlistExecutor** — full/chunked/sparse-aware data reading from disk image
- [x] **Sparse file support** — `SparseHandler`, virtual/allocated sizing, zero-fill regions
- [x] **Runlist validation** — overlap detection, OOB protection, circular run detection
- [x] **Fragmented NTFS recovery** — multi-run reconstruction, extent merging, SHA-256 integrity
- [x] **Deleted non-resident recovery** — classification (recoverable / partially_recoverable / corrupted)
- [x] **NTFS recovery CLI** — `recoverx ntfs recover` with rich output and JSON reporting
- [x] **Runlist analysis CLI** — `recoverx ntfs analyse --record N` with VCN/LCN/sparse/validation details
- [x] **MFT record enhancements** — `has_non_resident_data`, `is_fragmented`, `data_non_resident`
- [x] **332 tests** — flake8 / mypy / bandit clean (58 source files)

## v0.7.0 — NTFS Journaling & Timeline Forensics ✅

- [x] **Forensic Event Abstraction Layer** — `ForensicEvent` base class, `EventType`/`EventSource`/`Confidence` enums, factory functions
- [x] **Timeline Engine** — chronological sorting, dedup, filter, JSON/CSV/text export, metadata tracking
- [x] **Correlation Engine** — MFT↔USN matching, rename chains, file history, confidence scoring
- [x] **USN Journal Parser** — $UsnJrnl V2/V3 record parsing, 24 reason flags, live image reading
- [x] **USN → ForensicEvent mapping** — create/delete/rename/modify/security/close events from USN
- [x] **$LogFile Foundation** — restart pages (RSTR), log records (RCRD), 16 operation types, target MFT extraction
- [x] **Forensic CLI** — `recoverx forensic timeline`, `recoverx ntfs usn`, `recoverx ntfs logfile`
- [x] **Forensic reporting** — JSON timeline, CSV export, chronological text output
- [x] **Forensic test suite** — 78 new tests (unit + fuzz)
- [x] **Architecture registries** — `FORENSIC_REGISTRY` integration

## v0.7.5 — Advanced Journaling & Correlation ✅

- [x] **Bifragment gap carving** — locate header and footer with known gap
- [x] **Smart fragment reassembly** — scoring/ranking candidate fragments
- [x] **Metadata recovery from carving context** — embedded EXIF, document properties
- [x] **Timestamp extraction** — file system timestamps near carved regions
- [x] **Carving statistics** — fragmentation ratio, completeness estimate
- [x] **Validation hooks** — post‑carve integrity checks (CRC, image dimensions, etc.)

## v0.8.0 — Advanced Correlation & Distributed Forensics ✅

- [x] **Advanced Correlation Engine V2** — multi-source correlation, rename chains, delete/recreate, anomaly detection, heuristic rules, confidence scoring
- [x] **Event Graph Engine** — `CorrelationGraph` with nodes/edges, BFS traversal, path finding, anomaly clustering
- [x] **Distributed Indexing Foundation** — `Coordinator`, `Worker`, `TaskQueue`, `Scheduler`, priority-based scheduling, retry logic
- [x] **Remote Acquisition Foundation** — `AcquisitionSession`, `AcquisitionTarget`, `ImageStream`, `TransportInterface`, read-only guarantees
- [x] **Plugin SDK** — `Plugin` base class, `PluginRegistry`, `PluginLoader`, typed interfaces, lifecycle management
- [x] **Analyzer Framework** — `MassDeleteAnalyzer`, `SuspiciousRenameAnalyzer`, `TimestampAnomalyAnalyzer`, `DuplicateActivityAnalyzer`, `OrphanArtifactAnalyzer`
- [x] **Forensic Findings Engine** — `FindingsEngine`, `Finding` with severity/confidence/evidence chains, category classification
- [x] **Query Optimization Layer** — `QueryPlanner` with filter pushdown, cost estimation; `QueryCache` with TTL; `MetricsCollector`
- [x] **Forensic Export System** — `ForensicBundle`, `SQLitePackage` with chain-of-custody metadata and integrity verification
- [x] **Performance & Scalability** — `StreamingIndexer`, `IncrementalIndexer`, `ParallelAnalyzer`, `MemoryPressureGuard`
- [x] **CLI Expansion** — `recoverx forensic findings`, `recoverx forensic graph`, `recoverx plugins list`, `recoverx case create/open/list/close/delete`
- [x] **Registry Expansion** — `FORENSIC_REGISTRY` entries for analyzers, plugins, exporters, distributed workers, acquisition providers
- [x] **Fuzz Testing Expansion** — 51 new fuzz tests for query optimizer (planner, cache concurrency, metrics)
- [x] **954 tests** — flake8 / mypy / bandit clean (74 source files)
- [x] **Version 0.8.0** — Release title: "Advanced Correlation & Distributed Forensics"

## v0.8.1 — PyPI Distribution ✅

- [x] **Trusted Publishing** — published via GitHub Actions with `pypa/gh-action-pypi-publish` and `id-token: write`
- [x] **Open source governance** — `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`
- [x] **Documentation** — quickstart, architecture, plugin dev, forensic workflows
- [x] **Examples** — programmatic carving, timeline analysis, custom plugins, benchmarks
- [x] **PyPI availability** — `pip install recoverx` works globally
- [x] **975 tests** — all passing, backward compatible

## v0.8.2 — UX, Performance & Real-World Scan Experience ✅

- [x] **Professional Progress Engine** — `ScanProgress` with scanned/total, MB/s, ETA, findings by type, thread-safe, Rich live display
- [x] **Quick Scan Mode** (`--quick`) — prioritises MFT, boot sector, tail regions via `QuickScanStrategy`
- [x] **ScanStrategy abstraction** — `ScanStrategy` ABC with `FullScanStrategy` and `QuickScanStrategy`
- [x] **Scan Limits** (`--max-size`, `--max-time`) — graceful stop with partial results preserved
- [x] **Graceful Interruptions** — CTRL+C handling, safe worker shutdown, summary preserved
- [x] **Live Findings Preview** (`--live-findings`) — real-time discoveries during scan
- [x] **Output Directory** (`--output` / `-o`) — custom output dir with auto-creation
- [x] **Smart Type Filtering** (`--type`) — activate only selected carvers (jpg,png,pdf, etc.)
- [x] **981 tests** — flake8 / mypy / bandit clean, backward compatible

## v0.9.0 — SSD & Modern Hardware 🔬

- [ ] **Research TRIM/unmap impact on carve success rates**
- [ ] **NVMe passthrough** — read NVMe namespaces directly
- [ ] **OPAL/self-encrypting drive awareness**
- [ ] **Flash Translation Layer considerations**
- [ ] **Wear‑leveling and its effect on residual data**

## v1.0.0 — Stable Professional Release 🔜

- [ ] **Plugin architecture** — load external carvers as Python entry points
- [ ] **Carving profiles** — `--profile photo`, `--profile documents`, `--profile all`
- [ ] **Report generation** — JSON, CSV, HTML summaries of recovered files
- [ ] **Recovery session save/restore** — resume interrupted scans
- [ ] **Hashing** — SHA‑256 / SHA‑3 of every carved file for integrity verification
- [ ] **Input validation** — automatic image type detection, sanity checks
- [ ] **i18n / i18n-ready** — translatable CLI messages
- [ ] **API stability guarantee** — public API surface documented

## Future Research Areas 🔬

- **Carving without footers** — statistical / entropy-based file extraction
- **Deep learning for file classification** — CNN-based fragment identification
- **GPU‑accelerated pattern matching** — OpenCL / CUDA carving kernels
- **Cloud storage forensics** — carve from cloud snapshot images
- **Live memory carving** — carve from RAM dumps (volatility-style)

---

_Last updated: 2026-05-14_ (v0.7.5 completed)
