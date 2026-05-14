# RecoverX

Professional file recovery and carving tool for disk images and block devices.

Extracts deleted files from raw disk images (.img, .dd, .raw) using
signature-based file carving. Extensible architecture supports adding new
file formats with minimal code.

## Installation

```bash
# Clone and install
git clone <url> recoverx
cd recoverx
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# (Optional) dev dependencies for linting and testing
pip install -e ".[dev]"
```

## Usage

```bash
# Show connected disks and partitions
recoverx info

# Scan a disk image for recoverable files
recoverx scan sample.img
```

### Commands

| Command          | Description                                      |
|------------------|--------------------------------------------------|
| `recoverx info`  | List connected disks, partitions, block devices  |
| `recoverx scan`  | Scan image/device and carve recoverable files    |

## Development

### Setup

```bash
source .venv/bin/activate
pip install -e ".[dev]"
```

### Linting

```bash
black src/ tests/
isort src/ tests/
flake8 src/ tests/
```

### Testing

```bash
pytest -v
```

### Generate test image

```bash
python tests/create_sample.py
recoverx scan sample.img
```

## Supported formats

| Format | Status     |
| ------ | ---------- |
| JPEG   | ✅ Working |
| PNG    | 🔜 Planned |
| PDF    | 🔜 Planned |
| ZIP    | 🔜 Planned |
| NTFS   | 🔜 Planned |
| FAT32  | 🔜 Planned |

## Architecture

```
recoverx/
├── src/
│   └── recoverx/
│       ├── cli/              # CLI entry points (Typer)
│       │   ├── main.py       #       — app definition, info & scan commands
│       │   └── commands/
│       │       ├── info.py   #       — disk info display
│       │       └── scan.py   #       — carving pipeline
│       ├── core/
│       │   ├── disk/         # Disk/partition detection (psutil)
│       │   ├── carving/      # Signature-based file carvers
│       │   │   ├── base.py   #       — BaseCarver ABC + CarvedFile/FileSignature
│       │   │   ├── jpg.py    #       — JPEG carver (FFD8FF / FFD9)
│       │   │   └── signatures.py  # — signature registry
│       │   ├── recovery/     # Output file management
│       │   └── utils/        # RawReader, logging, helpers
├── tests/                    # pytest test suite
├── recovered/                # Carved file output (gitignored)
├── logs/                     # Log files (gitignored)
├── signatures/               # Format signature definitions
├── pyproject.toml
└── requirements.txt
```

## Adding a new format

1. Add a `FileSignature` entry in `src/recoverx/core/carving/signatures.py`
2. Create a carver class in `src/recoverx/core/carving/` extending `BaseCarver`
3. Register in the carving pipeline (`cli/commands/scan.py`)

Example for PNG:

```python
# signatures.py
SIGNATURES["png"] = FileSignature(
    name="PNG", extension="png",
    header=b"\x89PNG\r\n\x1a\n",
    footer=b"\x00\x00\x00\x00IEND\xae\x42\x60\x82",
)

# png.py
class PNGCarver(BaseCarver):
    def __init__(self):
        super().__init__(SIGNATURES["png"])
    def carve(self, data):
        # implementation
```

## License

MIT
