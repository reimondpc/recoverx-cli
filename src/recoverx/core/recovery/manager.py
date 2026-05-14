"""Recovery manager for saving carved files to disk.

Handles output directory creation, file naming (with auto-incrementing
counters per extension), and keeps a tally of recovered files.
"""

from pathlib import Path

from ..carving.base import CarvedFile


class RecoveryManager:
    """Manages the output of carved files to the recovered/ directory.

    Usage:
        mgr = RecoveryManager()
        path = mgr.save(carved_file)
    """

    def __init__(self, output_dir: str = "recovered") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._counter: dict[str, int] = {}

    def save(self, carved: CarvedFile) -> Path:
        """Write a CarvedFile to disk and return the output path.

        Files are named as ``{format}_{counter:03d}.{ext}``
        (e.g., ``jpg_001.jpg``) to keep naming predictable and sorted.
        """
        ext = carved.extension
        self._counter[ext] = self._counter.get(ext, 0) + 1
        filename = f"{carved.signature_name.lower()}_{self._counter[ext]:03d}.{ext}"
        path = self.output_dir / filename
        path.write_bytes(carved.data)
        return path

    @property
    def total_files(self) -> int:
        return sum(self._counter.values())
