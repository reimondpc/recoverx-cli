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
    "png": FileSignature(
        name="PNG",
        extension="png",
        header=b"\x89PNG\r\n\x1a\n",
        footer=b"\x00\x00\x00\x00IEND\xae\x42\x60\x82",
        min_size=67,
    ),
    "gif": FileSignature(
        name="GIF",
        extension="gif",
        header=b"GIF8",
        footer=b"\x00\x3b",
        min_size=43,
    ),
    "bmp": FileSignature(
        name="BMP",
        extension="bmp",
        header=b"BM",
        footer=None,
        min_size=54,
    ),
    "pdf": FileSignature(
        name="PDF",
        extension="pdf",
        header=b"%PDF",
        footer=b"%%EOF",
        min_size=1024,
    ),
}
