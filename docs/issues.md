# Initial Issues

Suggested first issues for the RecoverX project.  Each entry can be copied
directly into a GitHub issue.

---

## Issue 1 — Add PNG carver

**Labels:** `enhancement`, `good first issue`

**Description:**

Implement a PNG carver using the standard PNG signature:

- Header: `\x89PNG\r\n\x1a\n` (8 bytes)
- Footer: `\x00\x00\x00\x00IEND\xae\x42\x60\x82` (12 bytes — CRC included)

Follow the existing `JPEGCarver` pattern:

1. Add a `FileSignature` entry in `core/carving/signatures.py`
2. Create `core/carving/png.py` extending `BaseCarver`
3. Add a `PNGCarver` run in `cli/commands/scan.py`
4. Add tests in `tests/test_png_carver.py`

**Acceptance criteria:**

- [ ] `PNGCarver.carve()` returns `CarvedFile` instances for data containing PNG markers
- [ ] Carver respects `min_size` (at least 67 bytes for a valid PNG)
- [ ] No false positives on random data
- [ ] Tests pass

---

## Issue 2 — Add PDF carver

**Labels:** `enhancement`

**Description:**

Implement a PDF carver using:

- Header: `%PDF` (at offset 0 of the file)
- Footer: `%%EOF`

PDF files can contain multiple `%%EOF` markers (incremental saves). The carver
should handle the outermost `%%EOF`.

**Acceptance criteria:**

- [ ] `PDFCarver.carve()` extracts PDF content between `%PDF` and final `%%EOF`
- [ ] `min_size` set appropriately (≥ 1 KB)
- [ ] Tests pass

---

## Issue 3 — Implement chunked streaming scanner

**Labels:** `enhancement`, `performance`

**Description:**

The current scanner loads the entire image into memory (`bytearray`). For large
disks (100 GB+) this is not viable.

Implement a chunked scanner that:

1. Reads the image in fixed-size chunks (e.g., 4 MB)
2. Maintains an overlap buffer equal to the maximum carving window
3. Detects headers across chunk boundaries
4. Accumulates file data across chunks until the footer is found

**Design notes:**

- The overlap size must be at least as large as the max file size the carver
  should detect
- For JPEG this is currently `CARVER_LOOKBACK = 4 MB`
- Use `RawReader.read_at()` with a sliding offset

**Acceptance criteria:**

- [ ] Can scan a 1 GB test image without OOM
- [ ] Correctly carves files that span chunk boundaries
- [ ] Backward compatible — same results as the in-memory scan
- [ ] Progress bar reports meaningful percentage

---

## Issue 4 — Add `mmap`-based reader

**Labels:** `enhancement`, `performance`

**Description:**

On 64-bit systems, `mmap` can provide zero-copy access to disk images, reducing
memory overhead and improving random-access speed.

Create `MmapReader` (or extend `RawReader`) that:

- Uses `mmap.mmap()` on POSIX systems
- Falls back to the existing `RawReader` on platforms without `mmap`
- Supports the same `read_at(offset, size)` interface

**Acceptance criteria:**

- [ ] `MmapReader` passes all existing `RawReader` tests
- [ ] Performance is equal to or better than `RawReader`
- [ ] Fallback works on non-POSIX platforms

---

## Issue 5 — Add SHA-256 hashing for recovered files

**Labels:** `enhancement`, `forensics`

**Description:**

Forensic workflows require integrity verification. Add optional SHA-256 hashing
to the `RecoveryManager`:

- `--hash` flag on `recoverx scan`
- Saves a `recovered/hashes.sha256` file alongside carved files
- Each line: `<sha256>  <filename>`

**Acceptance criteria:**

- [ ] `--hash` flag implemented
- [ ] Hash file generated with proper SHA-256SUM format
- [ ] No performance impact when `--hash` is not used

---

## Issue 6 — Add benchmark suite

**Labels:** `enhancement`, `testing`

**Description:**

Create a `tests/benchmarks/` directory with a `conftest.py` that generates large
(100 MB–1 GB) test images with known embedded files.

Benchmarks should measure:

- Scan throughput (MB/s)
- Carving accuracy (precision / recall)
- Memory usage (peak RSS)

Use `pytest-benchmark` if appropriate.

**Acceptance criteria:**

- [ ] Benchmarks runnable via `pytest benchmarks/`
- [ ] Results are reported in a machine-readable format
- [ ] Baseline numbers are documented in `docs/benchmarks.md`

---

## Issue 7 — Add multithreaded carving

**Labels:** `enhancement`, `performance`

**Description:**

Independent file searches can be parallelised:

1. **Reader thread** — reads chunks and puts them on a queue
2. **Carver workers** (N = CPU count) — pop chunks, scan independently,
   push results to an output queue
3. **Writer thread** — pops results and saves via `RecoveryManager`

**Design notes:**

- Header detection and file accumulation must be atomic per chunk
- The output queue must be thread-safe (use `queue.Queue`)
- Add `--threads` CLI flag, defaulting to `os.cpu_count()`

**Acceptance criteria:**

- [ ] Linear (or near-linear) speedup with additional threads on multi-core
- [ ] Deterministic output — same files regardless of thread count
- [ ] Graceful handling of `KeyboardInterrupt`

---

## Issue 8 — Improve logging with structured output

**Labels:** `enhancement`

**Description:**

Add structured logging support for integration with forensic pipelines:

- Optional JSON log output (`--log-format json`)
- Log levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`
- Each log entry: `timestamp`, `level`, `module`, `message`, `extra`

**Acceptance criteria:**

- [ ] `--log-format json` flag on `recoverx scan`
- [ ] Valid JSON output suitable for ingestion by SIEM / log aggregators
- [ ] Backward compatible — default format remains unchanged

---

## Issue 9 — Add hexadecimal viewer for raw offsets

**Labels:** `enhancement`

**Description:**

Forensic examiners often need to inspect raw bytes at a specific offset.
Add a `recoverx hexdump <path> --offset <N> --length <L>` command that prints
a formatted hexdump (similar to `xxd` or `hexdump -C`).

**Acceptance criteria:**

- [ ] `recoverx hexdump` command exists
- [ ] Output format matches `hexdump -C` convention
- [ ] Works with both files and block devices
- [ ] Respects `--offset` and `--length` arguments

---

## Issue 10 — Add recovery statistics and summary reporting

**Labels:** `enhancement`

**Description:**

After a scan, provide a detailed summary:

- Total bytes scanned
- Total files found (by type)
- Total bytes recovered
- Elapsed time
- Throughput (MB/s)
- Files rejected (too small, corrupt header, etc.)

Output to console (Rich table) and optionally to JSON (`--report report.json`).

**Acceptance criteria:**

- [ ] Summary table shown after every scan
- [ ] `--report` flag writes JSON report to file
- [ ] Stats include successes, failures, and skipped
