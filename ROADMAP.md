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

## v0.7.0 — Fragmented & Advanced Recovery 🔜

- [ ] **Bifragment gap carving** — locate header and footer with known gap
- [ ] **Smart fragment reassembly** — scoring/ranking candidate fragments
- [ ] **Metadata recovery from carving context** — embedded EXIF, document properties
- [ ] **Timestamp extraction** — file system timestamps near carved regions
- [ ] **Carving statistics** — fragmentation ratio, completeness estimate
- [ ] **Validation hooks** — post‑carve integrity checks (CRC, image dimensions, etc.)

## v0.8.0 — SSD & Modern Hardware 🔬

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

_Last updated: 2026-05-14_
