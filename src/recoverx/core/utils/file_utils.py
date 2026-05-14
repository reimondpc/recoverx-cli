"""File and size utility functions."""


def format_size(bytes_size: int) -> str:
    """Convert a byte count to a human-readable string (e.g., '1.5 GB')."""
    size = float(bytes_size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"
