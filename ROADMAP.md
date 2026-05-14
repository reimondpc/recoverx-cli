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

## v0.3.0 — Additional Carvers 🔜

- [ ] **PNG carver** — signature `\x89PNG\r\n\x1a\n` / `IEND`
- [ ] **PDF carver** — signature `%PDF` / `%%EOF`
- [ ] **ZIP carver** — signature `PK\x03\x04`
- [ ] **GIF carver** — signature `GIF8`
- [ ] **BMP carver** — signature `BM`
- [ ] **Office docs** — OLE2 (`\xD0\xCF\x11\xE0`) based files (`.doc`, `.xls`, `.ppt`)
- [ ] **Enhanced signature registry** — offset-based headers, footer-less carving fallback
- [ ] **Auto‑register** carvers from a plugin folder

## v0.4.0 — Performance & Streaming 🔜

- [ ] **Chunked streaming scanner** — process arbitrarily large images with bounded memory
- [ ] **Sliding window overlap** — handle cross-boundary headers/footers
- [ ] **`mmap`-based reader** — zero-copy reads for supported platforms
- [ ] **Configurable chunk size** — CLI flag `--chunk-size`
- [ ] **Progress granularity** — per-chunk vs per-sector reporting
- [ ] **Cancellation support** — `KeyboardInterrupt` safe‑stop mid‑scan
- [ ] **Resource limits** — `--max-memory`, `--max-time` guards

## v0.5.0 — Multithreading 🔜

- [ ] **Parallel carving engine** — distribute independent file searches across workers
- [ ] **Producer‑consumer pipeline** — reader thread → carving workers → recovery writer
- [ ] **Thread‑safe RecoveryManager** — ordered output with concurrent saves
- [ ] **Benchmark suite** — measure throughput vs. thread count vs. chunk size
- [ ] **`--threads` / `--jobs` CLI flag**
- [ ] **Auto‑detect CPU count** default

## v0.6.0 — Filesystem Awareness 🔜

- [ ] **MBR / GPT partition table parser**
- [ ] **FAT32 reader** — cluster chains, directory entries, long file names
- [ ] **exFAT reader**
- [ ] **NTFS reader** — `$MFT`, attributes, resident/non-resident data
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
