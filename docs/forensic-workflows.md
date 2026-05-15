# Forensic Workflows

## Timeline Analysis

```bash
# Index an image for fast searching
recoverx forensic index case_image.dd

# Build a timeline
recoverx forensic timeline case_image.dd --since "2024-01-01" --format json

# Search for specific artifacts
recoverx forensic search case_image.dd --name "*.pdf"
recoverx forensic search case_image.dd --event FILE_DELETED
recoverx forensic search case_image.dd --hash d41d8cd98f00b204e9800998ecf8427e

# Run forensic analyzers
recoverx forensic findings case_image.dd

# Query with filters
recoverx forensic query case_image.dd "event_type = FILE_RENAMED AND filename LIKE '%.tmp'"
```

## File Carving

```bash
# Recover JPEG files
recoverx scan image.dd --output recovered/

# Recover specific types
recoverx scan image.dd --output pdfs/ --chunk-size 1

# Use thread pool for performance
recoverx scan image.dd --output recovered/ --threads 8
```

## Case Management

```bash
recoverx case create "Investigation-2024-001"
recoverx case open "Investigation-2024-001"
recoverx case list
```

## Evidence Export

```bash
recoverx forensic export image.dd --format sqlite --output evidence.db
```

## Distributed Processing

```bash
# Configure worker nodes
recoverx forensic distributed start --workers 4
```
