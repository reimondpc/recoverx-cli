# Architecture

RecoverX is organized as a modular, layered forensic toolkit.

## Layer Structure

```
recoverx/
├── cli/          # Command-line interface (Typer-based)
├── core/
│   ├── acquisition/   # Disk imaging and streaming
│   ├── analyzers/     # Behavioral anomaly detection
│   ├── carving/       # Signature-based file carving
│   ├── correlation/   # Event correlation engine
│   ├── distributed/   # Distributed task processing
│   ├── export/        # Evidence packaging (SQLite)
│   ├── filesystems/   # Filesystem parsers (NTFS, FAT32)
│   ├── findings/      # Findings management
│   ├── forensics/     # Timeline, indexing, querying
│   ├── optimizer/     # Query optimization
│   └── plugins/       # Plugin infrastructure
├── plugins/           # Plugin loader and interfaces
```

## Key Design Principles

- **Pluggable**: All analyzers and filesystem parsers are registered via plugin interfaces.
- **Streaming**: Carving and scanning operate on streams, not full in-memory copies.
- **Modular**: Each core module is self-contained with its own test suite.
- **CLI-first**: All functionality is exposed through the Typer CLI.
