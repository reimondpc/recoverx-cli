from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from recoverx.core.forensics.models import EventSource, EventType, ForensicEvent


@dataclass
class RenameChain:
    mft_reference: int
    filenames: list[str] = field(default_factory=list)
    events: list[ForensicEvent] = field(default_factory=list)
    timestamps: list[datetime] = field(default_factory=list)
    confidence: float = 0.8

    def add_event(self, event: ForensicEvent) -> None:
        self.events.append(event)
        if event.filename and event.filename not in self.filenames:
            self.filenames.append(event.filename)
        if event.timestamp:
            self.timestamps.append(event.timestamp)

    @property
    def rename_count(self) -> int:
        return len(self.filenames) - 1 if self.filenames else 0

    @property
    def duration(self) -> timedelta | None:
        if len(self.timestamps) >= 2:
            return self.timestamps[-1] - self.timestamps[0]
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mft_reference": self.mft_reference,
            "filenames": self.filenames,
            "rename_count": self.rename_count,
            "duration": str(self.duration) if self.duration else None,
            "confidence": self.confidence,
            "events": len(self.events),
        }


@dataclass
class DeleteRecreateChain:
    mft_reference: int
    filename: str
    deletes: list[ForensicEvent] = field(default_factory=list)
    creates: list[ForensicEvent] = field(default_factory=list)
    gaps: list[float] = field(default_factory=list)

    def add_delete(self, event: ForensicEvent) -> None:
        self.deletes.append(event)

    def add_create(self, event: ForensicEvent) -> None:
        self.creates.append(event)

    @property
    def cycle_count(self) -> int:
        return min(len(self.deletes), len(self.creates))

    def to_dict(self) -> dict[str, Any]:
        return {
            "mft_reference": self.mft_reference,
            "filename": self.filename,
            "cycle_count": self.cycle_count,
            "gaps": self.gaps,
        }


@dataclass
class OverwriteChain:
    mft_reference: int
    filename: str
    events: list[ForensicEvent] = field(default_factory=list)
    overwrite_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "mft_reference": self.mft_reference,
            "filename": self.filename,
            "overwrite_count": self.overwrite_count,
            "events": len(self.events),
        }


class ChainBuilder:
    def __init__(self) -> None:
        self._rename_chains: dict[int, RenameChain] = {}
        self._delete_recreate: dict[str, DeleteRecreateChain] = {}
        self._overwrite_chains: dict[int, OverwriteChain] = {}

    def build_rename_chains(self, events: list[ForensicEvent]) -> list[RenameChain]:
        by_mft: dict[int, list[ForensicEvent]] = {}
        for e in events:
            if e.mft_reference > 0:
                by_mft.setdefault(e.mft_reference, []).append(e)
        for mft_ref, file_events in by_mft.items():
            sorted_events = sorted(file_events, key=lambda x: x.timestamp or datetime.min)
            names_seen: list[str] = []
            chain = RenameChain(mft_reference=mft_ref)
            for e in sorted_events:
                if e.event_type == EventType.FILE_RENAMED or (
                    names_seen and e.filename and e.filename != names_seen[-1]
                ):
                    chain.add_event(e)
                    if e.filename and e.filename not in names_seen:
                        names_seen.append(e.filename)
            if chain.rename_count > 0 or len(chain.events) > 1:
                self._rename_chains[mft_ref] = chain
        return list(self._rename_chains.values())

    def build_delete_recreate(self, events: list[ForensicEvent]) -> list[DeleteRecreateChain]:
        by_mft: dict[int, list[ForensicEvent]] = {}
        for e in events:
            if e.mft_reference > 0:
                by_mft.setdefault(e.mft_reference, []).append(e)
        for mft_ref, file_events in by_mft.items():
            sorted_events = sorted(file_events, key=lambda x: x.timestamp or datetime.min)
            filename = sorted_events[0].filename if sorted_events else ""
            key = f"{mft_ref}:{filename}"
            chain = DeleteRecreateChain(mft_reference=mft_ref, filename=filename)
            for i in range(len(sorted_events) - 1):
                a, b = sorted_events[i], sorted_events[i + 1]
                if (
                    a.event_type == EventType.FILE_DELETED
                    and b.event_type == EventType.FILE_CREATED
                ):
                    if a.timestamp and b.timestamp and a.filename == b.filename:
                        gap = (b.timestamp - a.timestamp).total_seconds()
                        chain.add_delete(a)
                        chain.add_create(b)
                        chain.gaps.append(gap)
            if chain.cycle_count > 0:
                self._delete_recreate[key] = chain
        return list(self._delete_recreate.values())

    def get_rename_chain(self, mft_ref: int) -> RenameChain | None:
        return self._rename_chains.get(mft_ref)

    def get_delete_recreate(self, key: str) -> DeleteRecreateChain | None:
        return self._delete_recreate.get(key)
