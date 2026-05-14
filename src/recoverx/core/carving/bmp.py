import struct

from .base import BaseCarver, CarvedFile
from .signatures import SIGNATURES

CARVER_LOOKBACK = 4 * 1024 * 1024


class BMPCarver(BaseCarver):
    def __init__(self) -> None:
        super().__init__(SIGNATURES["bmp"])

    def carve(self, data: bytes) -> list[CarvedFile]:
        min_size = self.signature.min_size
        header = self.signature.header
        results: list[CarvedFile] = []
        offset = 0

        while offset < len(data):
            start = data.find(header, offset)
            if start == -1:
                break

            if len(data) - start < 6:
                offset = start + 1
                continue

            declared_size = struct.unpack_from("<I", data, start + 2)[0]

            if declared_size <= min_size or declared_size > len(data) - start:
                if declared_size > CARVER_LOOKBACK:
                    offset = start + 1
                    continue
                end = start + declared_size
            else:
                end = start + declared_size

            if end > len(data) or end <= start:
                offset = start + 1
                continue

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
