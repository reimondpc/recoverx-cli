# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
