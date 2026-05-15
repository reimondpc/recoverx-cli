# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.0] - 2026-05-14

### Added

- **Forensic Event Abstraction Layer** — `core/forensics/` package with `ForensicEvent` dataclass, `EventType`/`EventSource`/`Confidence` enums, event factory functions, timeline builder, correlation engine, artifact extractors, forensic source registry
- **USN Journal Parser** — `ntfs/usn/` subpackage with `USNRecord` V2/V3 parsing, USN reason flags (create/delete/rename/modify/security/close), `USNParser` class reading from live disk images via `$Extend\$UsnJrnl`, raw record iteration
- **USN → ForensicEvent mapping** — `usn/mapping.py` translates USN records to unified forensic events with rename-pair correlation, close detection, confidence scoring
- **$LogFile Foundation** — `ntfs/logfile/` subpackage with restart page parsing (RSTR), restart area extraction, log record parsing (RCRD), 16 operation types (InitializeFileRecord, UpdateResidentValue, UpdateMappingPairs, etc.), basic target MFT reference extraction
- **Timeline Engine** — chronological sorting, deduplication, event filtering (type/source/MFT/time/confidence), `to_json()`/`to_csv()`/`print_chronological()` export, comprehensive metadata tracking
- **Forensic Correlation Engine** — MFT↔USN cross-source matching within configurable time windows, rename chain reconstruction, file history tracking, confidence boosting on correlation
- **Forensic CLI** — `recoverx forensic timeline <image>` with `--since`, `--until`, `--format`, `--output`, `--limit`, `--json` options; chronological output with source tagging
- **NTFS USN CLI** — `recoverx ntfs usn <image>` with table output, reason flag display, JSON export
- **NTFS LogFile CLI** — `recoverx ntfs logfile <image>` with restart area info, log record listing, operation type display, JSON export
- **Forensic test suite** — 78 new tests (24 forensic events/timeline, 20 USN parsing, 16 LogFile parsing, 18 fuzz: 11 USN + 7 LogFile)
- **Fuzz testing** — malformed USN records, corrupted LogFile pages, extreme LSNs, oversized filenames, boundary conditions, random corruption — all with bounded memory and no infinite loops

### Infrastructure

- 418 total pytest tests (78 forensic + fuzz + 8 CLI integration)
- Flake8, mypy, bandit — all passing
- Version bumped to 0.7.0

## [0.6.5] - 2026-05-14

### Added

- **Runlist execution engine** — `runlists/` subpackage with `DataRun` dataclass, `resolve_runlist()` (VCN→LCN translation, sparse detection), `vcn_to_lcn()`, `runs_to_byte_offsets()`, `decode_runlist_entry()`
- **RunlistExecutor** — `execute()` (full data read), `execute_chunked()` (generator), `execute_sparse_aware()` (sparse-aware), `read_vcn_range()`, `read_clusters()`, `estimate_recoverable_bytes()`
- **Sparse file support** — `SparseHandler` with virtual/allocated size calculation, sparse ratio, region counting; `is_sparse_runlist()`, `count_sparse_regions()`, `count_allocated_regions()`
- **Runlist validation** — `validate_runlist()` (empty, VCN overlap, invalid LCN, LCN OOB, LCN overlap, impossible size, VCN exceeds total, zero cluster count), `check_circular_runs()`, `validate_data_run_integrity()`
- **Fragmented NTFS recovery** — multi-run reconstruction, extent merging, ordered recovery, SHA-256 integrity hashing
- **Deleted non-resident recovery** — recover files from deleted MFT records with non-resident DATA attributes; classification: recoverable / partially_recoverable / corrupted
- **NTFS file recovery CLI** — `recoverx ntfs recover` with `--deleted-only`, `--non-resident-only`, `--output`, `--json`, `--verify-hashes`, `--threads` options; rich output with status, run count, sparse indicators
- **NTFS analyse CLI** — `recoverx ntfs analyse --record N` for detailed runlist analysis (VCN/LCN mapping, fragmentation, sparse regions, validation issues, recoverable/lost bytes)
- **Advanced JSON reporting** — runs, integrity, fragments, sparse info in recovery output
- **MFT record enhancements** — `data_non_resident` field, `has_non_resident_data`, `is_fragmented` properties, `to_dict()` with non-resident details
- **`is_sparse` fix** — `parse_runlist()` now correctly distinguishes sparse runs from real runs with zero relative offset

### Infrastructure

- 332 total pytest tests (48 new: 27 runlist/mapping/validation, 17 non-resident recovery, 4 fuzz)
- Flake8, mypy (strict), bandit — all passing across 58 source files
- Version bumped to 0.6.5

## [0.6.0] - 2026-05-14

### Added

- **NTFS boot sector parser** — full BPB extraction (bytes/sector, clusters/FRS, MFT cluster, volume serial, OEM ID), validation, to_dict export
- **NTFS MFT record parser** — FILE record header parsing, fixup application, record flags (in_use, directory, deleted), attribute iteration
- **NTFS attribute system** — STANDARD_INFORMATION (timestamps, flags), FILE_NAME (parent ref, name, timestamps, sizes), DATA (resident extraction), non-resident runlist parser foundation
- **NTFS resident data recovery** — recover small files embedded in MFT records with SHA-256 hashing, recovery status, deleted detection
- **NTFS deleted entry detection** — walk MFT identifying FILE records with IN_USE=0, metadata extraction
- **NTFS MFT walker** — sequential record iteration with multi-sector fixup, validation, skip invalid
- **NTFS CLI** — `recoverx ntfs info` (boot sector details), `mft` (record listing), `deleted` (deleted entries), `resident` (extract small files) with `--json` output
- **NTFS test image generator** — `tests/ntfs/create_ntfs_images.py` produces valid NTFS images with known files and deleted entries
- **NTFS test suite** — 97 new tests (boot sector, MFT, attributes, fuzz) covering parsing, edge cases, malformed data
- **NTFS fuzz tests** — random corruption of boot sectors, MFT records, attributes, runlists, resident data, recovery

### Infrastructure

- 277 total pytest tests (97 new: 35 unit, 27 attribute, 22 fuzz, 13 boot sector)
- Flake8, mypy (strict), bandit — all passing across NTFS modules
- Version bumped to 0.6.0

## [0.5.5] - 2026-05-14

### Added

- **GitHub Actions CI/CD** — `ci.yml` (pytest + flake8 + black + isort + mypy + bandit on Python 3.10/3.11/3.12), `release.yml` (tag validation, version check, packaging verification)
- **Test coverage system** — `pytest-cov` configured for source coverage with terminal/XML/HTML reporting
- **Fuzz testing framework** — `tests/fuzz/test_fat32_fuzz.py` covers corrupted boot sectors, malformed directory entries, self-referencing FAT loops, bad clusters, random FAT chains, extreme BPB values, zero-size images, and memory safety edge cases
- **Stress datasets** — `tests/datasets/create_stress_images.py` generates fragmented images (50+ files), deep directories (20 levels), partially overwritten files, FAT self-loops, orphan clusters, and large images
- **Recovery validation suite** — `tests/validation/test_recovery_quality.py` measures precision, recovery rate, metadata integrity, hash consistency, and subdirectory traversal quality
- **Advanced logging** — FORENSIC level (15) added for audit-grade recovery trails; thread ID and logger name in file logs
- **Performance profiler** — `Profiler` context manager with CPU, RAM, and throughput metrics; `profile_operation` decorator for function-level profiling; JSON export
- **Architecture registries** — `scanner/__init__.py`, `filesystems/__init__.py`, `carving/__init__.py`, `reporting/__init__.py` with register/get/list for future plugin loading
- **Static analysis** — `mypy` (strict typing checks) and `bandit` (security scanning) configured in `pyproject.toml`

### Changed

- **Logger** — now accepts `console_level` and `file_level` parameters; FORENSIC level (15) for audit trails; enhanced file log format with thread IDs
- **Validate boot sector** — early return on `sectors_per_cluster == 0` to prevent `ZeroDivisionError` in `total_clusters`
- **Packaging** — `build` and `twine` added as dev dependencies; wheel and sdist verified clean

### Infrastructure

- 216 total pytest tests (29 new: 21 fuzz, 8 validation, stress dataset generators)
- Coverage: 81% overall, FAT32 critical modules >88%
- Version bumped to 0.5.5

## [0.5.0] - 2026-05-14

### Added

- **FAT32 boot sector parser** — `parse_boot_sector()` reads and validates BPB fields (OEM ID, cluster/sector geometry, FAT size, volume label, signature)
- **FAT32 directory traversal** — `parse_directory_entries()` decodes SFN + LFN (0x0F) entries, handles deleted markers (0xE5), free markers (0x00); `walk_directory_tree()` recursively visits subdirectories
- **FAT cluster chain reader** — `read_cluster_chain()` follows FAT32 FAT entries with loop/bad-cluster/free/zero detection; `read_cluster_data()` reads individual clusters; `read_chain_data()` aggregates cluster data
- **Deleted file recovery** — `FAT32Recovery.find_deleted_entries()` scans directory trees for 0xE5-marked entries; `recover_deleted_file()` reconstructs cluster chains, truncates to declared size, computes SHA-256
- **CLI commands** — `recoverx fat32 info`, `list`, `deleted`, `recover` with `--json` output for all subcommands
- **Test image generator** — `tests/fat32/create_fat32_image.py` builds reproducible FAT32 images with normal files, deleted files, subdirectories, and volume labels

### Changed

- **CLI** — `fat32` subcommand group registered via `app.add_typer(fat32_app)` in `main.py`

### Infrastructure

- 187 total pytest tests (76 new: FAT32 boot sector, FAT table, directory, recovery, integration, CLI)
- Version bumped to 0.5.0

## [0.4.0] - 2026-05-14

### Added

- **GIF carving** — `GIFCarver` supports both GIF87a and GIF89a formats with 4 MB lookback
- **BMP carving** — `BMPCarver` uses the file size declared in the BMP header to extract complete images
- **PDF carving** — `PDFCarver` extracts PDFs via `%PDF` / `%%EOF` markers with 8 MB lookback
- **Memory-mapped scanner** — `MmapScanner` uses `mmap` for zero-copy reads with automatic fallback to streaming on failure or huge files
- **Multithreaded scanner** — `ThreadedScanner` partitions images into overlapping regions and scans them in parallel; configurable thread count via `--threads`
- **Advanced benchmark** — `AdvancedBenchmark` tracks CPU%, peak RSS, files/min, and per-thread timing; exports to JSON
- **JSON forensic reports** — `JSONReport` writes structured output with `scan_info`, `benchmark`, and per-file metadata (offset, size, SHA‑256, path)
- **Filesystem detection** — automatic identification of FAT12/16/32, exFAT, NTFS, and ext2/3/4 from the boot sector / superblock (read-only)
- **Hash database** — persistent `HashDatabase` stores SHA‑256 digests across runs; provides dedup and statistics
- **Direct disk access** — `recoverx devices` command lists all connected disks and raw block devices with optional `--detailed` probe
- **Device validation** — scanning raw devices (`/dev/sdX`) shows safety warnings and permission checks

### Changed

- **CLI overhaul** — `recoverx scan` now accepts `--threads`, `--report`, `--no-mmap`, `--chunk-size` flags
- **Scan pipeline** — automatically selects the best scanner (threaded > mmap > streaming) based on source size and flags
- **Signature registry** — extended with GIF, BMP, PDF entries
- **Sample image generator** — now embeds GIF, BMP, and PDF test files alongside JPEGs and PNGs

### Infrastructure

- 111 total pytest tests (67 new: GIF, BMP, PDF carvers, mmap, threading, benchmark, reports, FS detection, hash DB, CLI)
- Cross-boundary file detection tested with configurable chunk/overlap sizes
- Version bumped to 0.4.0

## [0.3.0] - 2026-05-14

### Added

- **PNG carving** — new `PNGCarver` using the standard PNG signature (`\x89PNG\r\n\x1a\n`) and IEND chunk marker (`\x00\x00\x00\x00IEND\xae\x42\x60\x82`)
- **SHA-256 hashing** — `HashManager` computes SHA-256 digests for every recovered file, displayed in CLI output and available for deduplication and integrity verification
- **Chunked streaming scanner** — `StreamingScanner` processes images in configurable chunks (default 4 MB) with overlapping windows so memory usage stays bounded regardless of source size
- **Scan benchmarking** — `ScanBenchmark` measures elapsed time, throughput (MB/s), and file count displayed at the end of every scan

### Changed

- **Scan pipeline** — `recoverx scan` now uses the streaming scanner with all registered carvers (JPEG + PNG), hashing, and benchmark reporting
- **Sample image generator** — `tests/create_sample.py` now embeds both JPEG and PNG test files

### Infrastructure

- 44 total pytest tests (21 new: PNG carver, hashing, streaming scanner)
- Cross-boundary file detection tested with configurable chunk/overlap sizes
- Version bumped to 0.3.0

## [0.2.0] - 2026-05-14

### Added

- **JPEG carving** — signature-based file extraction using SOI (`FFD8FF`) / EOI (`FFD9`) markers with configurable lookback window (4 MB)
- **RawReader** — read-only binary reader for disk images (`.img`, `.dd`, `.raw`) and block devices with sector-level and offset-level access
- **RecoveryManager** — auto-incrementing output file naming per extension, output directory creation
- **File signature registry** — centralised `SIGNATURES` dict in `core/carving/signatures.py` for easy format addition
- **BaseCarver ABC** — abstract base class enforcing a consistent `carve(data: bytes) -> list[CarvedFile]` interface
- **Disk detector** — `psutil`-based enumeration of mounted partitions plus raw block device discovery via `/sys/block` (Linux)
- **Typer CLI** — `recoverx info` and `recoverx scan <path>` commands with `--help`
- **Rich output** — colourised console, progress bars (`rich.progress`), formatted tables (`rich.table`)
- **Dual logging** — `RichHandler` for console (INFO+) and rotated file handler for `logs/recoverx.log` (DEBUG+)
- **`src/` layout** — standard Python `src/`-layout package with setuptools `packages.find`
- **pytest test suite** — 23 tests covering `RawReader`, `JPEGCarver`, `RecoveryManager`, and signature registry
- **Linting toolchain** — `black`, `isort`, `flake8` configured with consistent 100-char line length
- **Sample image generator** — `tests/create_sample.py` produces a 10 MB `.img` with two embedded JPEGs at known offsets

### Changed

- Migrated source tree from flat layout to `src/recoverx/` (src-layout)
- Refactored all cross-package imports from relative `from core.xxx` to absolute `from recoverx.core.xxx`
- Updated `pyproject.toml` for modern setuptools with `where = ["src"]` discovery

### Infrastructure

- `pyproject.toml` with build-system, dependencies, scripts, and tool configs
- `.gitignore` excluding virtual environments, build artifacts, test outputs, and disk images
- `requirements.txt` for quick dependency install without optional dev extras
- `.flake8` configuration for line-length and rule exclusions

## [0.1.0] - 2026-05-14

### Added

- Initial project scaffold
- CLI skeleton with Typer
- Core module structure

[0.2.0]: https://github.com/recoverx/recoverx/releases/tag/v0.2.0
[0.1.0]: https://github.com/recoverx/recoverx/releases/tag/v0.1.0
