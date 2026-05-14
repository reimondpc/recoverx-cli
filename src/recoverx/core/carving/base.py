"""Base classes and data types for the file carving system.

This module defines the abstract interface that all file carvers must
implement. New file formats (PNG, PDF, ZIP, etc.) can be added by
subclassing BaseCarver and registering a FileSignature.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CarvedFile:
    """Represents a single file recovered through carving.

    Attributes:
        data: Raw bytes of the recovered file.
        offset_start: Byte offset in the source where the file header was found.
        offset_end: Byte offset where the file footer ends.
        signature_name: Human-readable format name (e.g., 'JPEG').
        extension: File extension without dot (e.g., 'jpg').
    """

    data: bytes
    offset_start: int
    offset_end: int
    signature_name: str
    extension: str


@dataclass
class FileSignature:
    """Defines the binary signature of a file format.

    Attributes:
        name: Human-readable format name.
        extension: File extension (without dot).
        header: Byte sequence that marks the start of a file.
        footer: Optional byte sequence that marks the end of a file.
        min_size: Minimum valid file size in bytes (0 = no minimum).
        max_size: Maximum file size to attempt recovery (0 = unlimited).
    """

    name: str
    extension: str
    header: bytes
    footer: bytes | None = None
    min_size: int = 0
    max_size: int = 0


class BaseCarver(ABC):
    """Abstract base class for signature-based file carvers.

    Each subclass implements the carve() method to scan a byte buffer
    and return a list of CarvedFile instances.
    """

    def __init__(self, signature: FileSignature) -> None:
        self.signature = signature

    @abstractmethod
    def carve(self, data: bytes) -> list[CarvedFile]:
        """Scan *data* for files matching this carver's signature.

        Args:
            data: The raw byte buffer to scan (typically from a disk image).

        Returns:
            A list of CarvedFile instances found in the data.
        """
