from .base import BaseCarver, CarvedFile
from .signatures import SIGNATURES

CARVER_LOOKBACK = 4 * 1024 * 1024


class GIFCarver(BaseCarver):
    def __init__(self) -> None:
        super().__init__(SIGNATURES["gif"])

    def carve(self, data: bytes) -> list[CarvedFile]:
        footer = self.signature.footer
        if footer is None:
            return []

        min_size = self.signature.min_size
        results: list[CarvedFile] = []
        offset = 0

        while offset < len(data):
            start = data.find(b"GIF8", offset)
            if start == -1:
                break

            if len(data) <= start + 5:
                offset = start + 1
                continue

            version = data[start + 3 : start + 6]
            if version not in (b"87a", b"89a"):
                offset = start + 1
                continue

            search_limit = start + CARVER_LOOKBACK
            end = data.find(footer, start + 6)

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
