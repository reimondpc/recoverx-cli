"""Registry of known file signatures.

Centralised signature definitions make it trivial to add support for new
file formats. Each entry maps a short key to a FileSignature describing
the header/footer bytes and validation constraints.
"""

from .base import FileSignature

SIGNATURES: dict[str, FileSignature] = {
    "jpg": FileSignature(
        name="JPEG",
        extension="jpg",
        header=b"\xff\xd8\xff",
        footer=b"\xff\xd9",
        min_size=128,
    ),
    # Future formats:
    # "png":  FileSignature(name="PNG",  extension="png",  header=b"\x89PNG", ...),
    # "pdf":  FileSignature(name="PDF",  extension="pdf",  header=b"%PDF", ...),
    # "zip":  FileSignature(name="ZIP",  extension="zip",  header=b"PK\x03\x04", ...),
}
