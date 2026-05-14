from .base import BaseCarver, CarvedFile
from .signatures import SIGNATURES

CARVER_LOOKBACK = 8 * 1024 * 1024


class PDFCarver(BaseCarver):
    def __init__(self) -> None:
        super().__init__(SIGNATURES["pdf"])

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

            end = data.find(footer, start + len(header))

            if end == -1:
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
