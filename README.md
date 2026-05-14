<div align="center">
  <h1>RecoverX</h1>
  <p>
    <strong>Professional file recovery and carving tool for disk images and block devices.</strong>
  </p>
  <p>
    <img src="https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white" alt="Python 3.10+">
    <img src="https://img.shields.io/badge/pytest-187%20passing-green?logo=pytest" alt="pytest 187 passing">
    <img src="https://img.shields.io/badge/code%20style-black-000000?logo=black" alt="Code style: black">
    <img src="https://img.shields.io/badge/license-MIT-yellow?logo=open-source-initiative" alt="MIT License">
    <img src="https://img.shields.io/badge/status-MVP-brightgreen" alt="Status: MVP">
  </p>
</div>

---

RecoverX extracts deleted or lost files from raw disk images (`.img`, `.dd`, `.raw`)
and block devices using signature-based **file carving**. Its modular architecture
makes adding new file formats trivial — implement a single method and register a
signature.

---

## Features

- **JPEG carving** — extracts JPEG images via SOI (`FFD8FF`) / EOI (`FFD9`) marker detection with configurable lookback window
- **Raw image scanning** — read-only sector-level and offset-level access to disk images and physical block devices
- **Disk detection** — enumerate connected disks, partitions, and block devices with size, type, and mount point information
- **Read-only architecture** — every disk operation is strictly read-only; no writes to the source image
- **Modular carving engine** — `BaseCarver` ABC + `FileSignature` dataclass; add PNG/PDF/ZIP by creating one file
- **Rich CLI** — coloured output, live progress bars, formatted tables via `rich`
- **Dual logging** — console (INFO+) + structured file logs (DEBUG+)
- **Extensible** — drop-in carvers, centralised signature registry, recovery manager with auto-naming
- **PNG carving** — extracts PNG images via `\x89PNG` header / IEND footer signature matching
- **GIF carving** — supports both GIF87a and GIF89a formats
- **BMP carving** — uses file-size-from-header for accurate extraction
- **PDF carving** — extracts PDFs via `%PDF` / `%%EOF` markers
- **SHA-256 forensic hashing** — per-file SHA-256 hash displayed in CLI output; deduplication support
- **Hash database** — persistent SHA-256 hash storage across runs for dedup and statistics
- **Chunked streaming scanner** — memory-efficient, configurable chunk/overlap sizes (default 4 MB)
- **Memory-mapped scanner** — zero-copy reads with automatic fallback to streaming
- **Multithreaded scanner** — parallel region-based scanning with `--threads` CLI flag
- **Scan benchmarking** — elapsed time, MB/s, CPU%, RAM, files/min; exports to JSON
- **JSON forensic reports** — structured output usable in forensic pipelines (`--report report.json`)
- **Filesystem detection** — automatic identification of FAT12/16/32, exFAT, NTFS, ext2/3/4
- **Direct disk access** — `recoverx devices` lists connected disks; `recoverx scan /dev/sdX` reads raw devices (read-only)
- **FAT32 filesystem analysis** — boot sector parsing, directory traversal (SFN + LFN), cluster chain reading
- **FAT32 deleted file recovery** — scan for 0xE5-marked entries, reconstruct cluster chains, recover with SHA-256
- **FAT32 CLI** — `recoverx fat32 info`, `list`, `deleted`, `recover` with `--json` output
- **Testing suite** — 187 pytest tests across all core modules

## Installation

```bash
# Clone the repository
git clone https://github.com/recoverx/recoverx.git
cd recoverx

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install the package
pip install -e .

# (Optional) Development dependencies for linting and testing
pip install -e ".[dev]"
```

## Usage

```bash
# Show connected disks and partitions
recoverx info

# Scan a disk image for recoverable files
recoverx scan sample.img

# Show help
recoverx --help
```

### Commands

| Command          | Description                                      |
|------------------|--------------------------------------------------|
| `recoverx info`  | List connected disks, partitions, block devices  |
| `recoverx scan`  | Scan image/device and carve recoverable files    |

### Example output

```text
RecoverX — Scanning sample.img
  Size:    10.0 MB
  Sectors: 20,480

Reading image...
Reading... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 10.5/10.5 MB 0:00:00

Carving files...
  [+] JPEG found at offset 204,800
      SHA256: a1b2c3d4e5f6...
      Saved: recovered/jpeg_001.jpg
  [+] PNG found at offset 1,048,576
      SHA256: f6e5d4c3b2a1...
      Saved: recovered/png_001.png

                   Recovered Files
┏━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ # ┃ File         ┃               Offset ┃     Size ┃ SHA256                      ┃
┡━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 1 │ jpeg_001.jpg │    0x32000 (204,800) │ 1014.0 B │ a1b2c3d4e5f6...            │
│ 2 │ png_001.png  │ 0x100000 (1,048,576) │  2.5 KB  │ f6e5d4c3b2a1...            │
└───┴──────────────┴──────────────────────┴──────────┴────────────────────────────┘

Scan complete: 2 file(s) recovered in 0.32s (32.8 MB/s)
```

## Development

```bash
source .venv/bin/activate
pip install -e ".[dev]"
```

### Testing

```bash
pytest -v
```

### Linting and formatting

```bash
black src/ tests/
isort src/ tests/
flake8 src/ tests/
```

### Generate test image

```bash
python tests/create_sample.py
recoverx scan sample.img
```

## Architecture

```
recoverx/
├── src/
│   └── recoverx/
│       ├── __init__.py           # Package root
│       ├── cli/
│       │   ├── main.py           # Typer app, command registration
│       │   └── commands/
│       │       ├── info.py       # recoverx info — disk detection
│       │       └── scan.py       # recoverx scan — carving pipeline
│       └── core/
│           ├── disk/
│           │   └── detector.py   # psutil + /sys/block enumeration
│           ├── carving/
│           │   ├── base.py       # BaseCarver ABC + CarvedFile / FileSignature
│           │   ├── jpg.py        # JPEG carver (FFD8FF / FFD9)
│           │   ├── png.py        # PNG carver (\x89PNG / IEND)
│           │   ├── gif.py        # GIF carver (GIF87a / GIF89a)
│           │   ├── bmp.py        # BMP carver (BM + header size)
│           │   ├── pdf.py        # PDF carver (%PDF / %%EOF)
│           │   ├── streaming.py  # Chunked streaming scanner with overlap
│           │   └── signatures.py # Centralised signature registry
│           ├── scanner/
│           │   ├── mmap_scanner.py     # Memory-mapped scanner (zero-copy)
│           │   └── threaded_scanner.py # Parallel region-based scanner
│           ├── recovery/
│           │   └── manager.py    # Auto-named output, counter per extension
│           ├── reporting/
│           │   └── json_report.py # JSON forensic report generator
│           ├── benchmark/
│           │   └── advanced_benchmark.py # CPU/RAM/throughput metrics
│           ├── filesystems/
│           │   ├── detector.py   # FAT/NTFS/ext4/exFAT detection
│           │   └── fat32/        # FAT32 analysis and recovery
│           │       ├── boot_sector.py
│           │       ├── fat_table.py
│           │       ├── directory.py
│           │       └── recovery.py
│           └── utils/
│               ├── raw_reader.py # Read-only binary reader (offset/sector)
│               ├── logger.py     # Rich console + file dual logging
│               ├── hashing.py        # SHA-256 hashing, HashManager
│               ├── hash_database.py  # Persistent hash storage / dedup
│               ├── benchmark.py      # ScanBenchmark (elapsed, MB/s)
│               └── file_utils.py     # format_size helper
├── tests/                        # pytest suite (187 tests)
├── recovered/                    # Carved file output (gitignored)
├── logs/                         # Log files (gitignored)
├── signatures/                   # Format signature definitions
├── pyproject.toml
├── requirements.txt
├── CHANGELOG.md
├── LICENSE
└── README.md
```

### Key design decisions

- **`BaseCarver`** — abstract class that enforces a single `carve(data: bytes) -> list[CarvedFile]` contract. Every format-specific carver (JPEG, PNG, …) is a self-contained subclass.
- **`RawReader`** — context-managed, read-only binary reader. Works on both files and block devices. Provides `read_at(offset, size)` and `read_sector(sector)` for flexible access.
- **`RecoveryManager`** — tracks a counter per file extension so output names are deterministic (`jpeg_001.jpg`, `jpeg_002.jpg`, …). Output directory is created automatically.
- **Signature registry** — `signatures.py` is a single dict that maps format keys to `FileSignature` instances. Adding a format is a one-liner here plus a carver class.

## Adding a new file format

1. Add a `FileSignature` to `src/recoverx/core/carving/signatures.py`
2. Create a carver in `src/recoverx/core/carving/` that extends `BaseCarver`
3. Wire it into the scan pipeline in `cli/commands/scan.py`

```python
# signatures.py
SIGNATURES["png"] = FileSignature(
    name="PNG", extension="png",
    header=b"\x89PNG\r\n\x1a\n",
    footer=b"\x00\x00\x00\x00IEND\xae\x42\x60\x82",
    min_size=67,
)

# png.py
from .base import BaseCarver, CarvedFile
from .signatures import SIGNATURES

class PNGCarver(BaseCarver):
    def __init__(self):
        super().__init__(SIGNATURES["png"])

    def carve(self, data: bytes) -> list[CarvedFile]:
        # Implementation follows the same header/footer pattern as JPEGCarver
        ...
```

## Future roadmap

| Feature                 | Status     |
|-------------------------|------------|
| JPEG carving            | ✅ Done    |
| PNG carving             | ✅ Done    |
| GIF carving             | ✅ Done    |
| BMP carving             | ✅ Done    |
| PDF carving             | ✅ Done    |
| SHA-256 hashing         | ✅ Done    |
| Hash database           | ✅ Done    |
| Scan benchmarking       | ✅ Done    |
| Chunked streaming       | ✅ Done    |
| Memory-mapped scanner   | ✅ Done    |
| Multithreaded scanner   | ✅ Done    |
| JSON forensic reports   | ✅ Done    |
| Filesystem detection    | ✅ Done    |
| Direct disk access      | ✅ Done    |
| FAT32 parsing            | ✅ Done    |
| FAT32 file recovery      | ✅ Done    |
| ZIP carving              | 🔜 Planned |
| NTFS parsing             | 🔜 Planned |
| SSD/TRIM awareness       | 🔜 Planned |
| ReFS / APFS support  | 🔜 Planned |
| GUI (optional)       | 🔜 Planned |

## License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.
