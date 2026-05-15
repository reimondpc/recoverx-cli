# Quickstart

## Installation

```bash
pip install recoverx
```

## First Commands

### List connected devices

```bash
recoverx devices
```

### Scan a disk image for recoverable files

```bash
recoverx scan image.dd --output recovered/ --threads 4
```

### Analyze NTFS volume

```bash
recoverx ntfs info image.dd
recoverx ntfs mft image.dd --output mft_export.csv
```

### Build a forensic timeline

```bash
recoverx forensic timeline image.dd --since "2024-01-01" --format json
```

### Index and search events

```bash
recoverx forensic index image.dd
recoverx forensic search image.dd --name "*.pdf" --deleted-only
```

## Next Steps

- See `recoverx --help` for all commands
- Read `docs/architecture.md` for system design
- Read `docs/forensic-workflows.md` for investigation workflows
