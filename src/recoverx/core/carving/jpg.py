"""JPEG file carver.

Implements header/footer-based carving for JPEG images using the standard
SOI (FF D8 FF) and EOI (FF D9) markers. The carver limits the search
window to prevent runaway scans on corrupt data.
"""

from .base import BaseCarver, CarvedFile
from .signatures import SIGNATURES

CARVER_LOOKBACK = 4 * 1024 * 1024  # Maximum bytes to search for a footer after a header


class JPEGCarver(BaseCarver):
    """Carves JPEG files by locating SOI (FFD8FF) / EOI (FFD9) markers.

    Walks the input buffer linearly, recording every valid header/footer
    pair and extracting the bytes between them.
    """

    def __init__(self) -> None:
        super().__init__(SIGNATURES["jpg"])

    def carve(self, data: bytes) -> list[CarvedFile]:
        footer = self.signature.footer
        if footer is None:
            return []

        header = self.signature.header
        min_size = self.signature.min_size
        results: list[CarvedFile] = []
        offset = 0

        while offset < len(data):
            start = data.find(header, offset)
            if start == -1:
                break

            search_limit = start + CARVER_LOOKBACK
            end = data.find(footer, start + len(header))

            if end == -1 or end > search_limit:
                offset = start + 1
                continue

            end += len(footer)
            file_data = data[start:end]

            if len(file_data) >= min_size:
                results.append(
                    CarvedFile(
                        data=file_data,
                        offset_start=start,
                        offset_end=end,
                        signature_name=self.signature.name,
                        extension=self.signature.extension,
                    )
                )

            offset = end

        return results
