from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class StreamChunk:
    offset: int
    data: bytes
    chunk_index: int
    total_chunks: int

    @property
    def size(self) -> int:
        return len(self.data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "offset": self.offset,
            "size": self.size,
            "chunk_index": self.chunk_index,
            "total_chunks": self.total_chunks,
        }


class ImageStream:
    def __init__(self, source: str, chunk_size: int = 65536) -> None:
        self._source = source
        self._chunk_size = chunk_size
        self._offset = 0
        self._total_size: int | None = None
        self._closed = False

    @property
    def source(self) -> str:
        return self._source

    @property
    def chunk_size(self) -> int:
        return self._chunk_size

    @property
    def offset(self) -> int:
        return self._offset

    def read_chunk(self) -> StreamChunk | None:
        if self._closed:
            return None
        chunk_data = b""
        chunk_index = self._offset // self._chunk_size if self._chunk_size else 0
        chunk = StreamChunk(
            offset=self._offset,
            data=chunk_data,
            chunk_index=chunk_index,
            total_chunks=0,
        )
        self._offset += len(chunk_data)
        return chunk if chunk_data else None

    def seek(self, offset: int) -> None:
        self._offset = offset

    def close(self) -> None:
        self._closed = True

    @property
    def is_closed(self) -> bool:
        return self._closed
