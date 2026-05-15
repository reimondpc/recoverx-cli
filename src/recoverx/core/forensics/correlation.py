from __future__ import annotations

import logging
from datetime import datetime, timedelta

from .models import Confidence, EventSource, EventType, ForensicEvent

logger = logging.getLogger("recoverx")


class CorrelationEngine:
    def __init__(self) -> None:
        self._rename_chains: dict[int, list[ForensicEvent]] = {}
        self._file_history: dict[int, list[ForensicEvent]] = {}

    def correlate(self, events: list[ForensicEvent]) -> list[ForensicEvent]:
        correlated: list[ForensicEvent] = list(events)
        correlated = self._correlate_renames(correlated)
        correlated = self._deduplicate_events(correlated)
        return correlated

    def _correlate_renames(
        self, events: list[ForensicEvent],
    ) -> list[ForensicEvent]:
        by_mft: dict[int, list[ForensicEvent]] = {}
        for e in events:
            if e.mft_reference > 0:
                by_mft.setdefault(e.mft_reference, []).append(e)

        for mft_ref, file_events in by_mft.items():
            sorted_events = sorted(
                file_events, key=lambda x: x.timestamp or datetime.min
            )
            deletions_now_allowed = [
                e for e in sorted_events
                if e.event_type != EventType.FILE_DELETED
            ]
            self._rename_chains[mft_ref] = deletions_now_allowed

            self._file_history[mft_ref] = sorted_events

            for i in range(len(deletions_now_allowed) - 1):
                current = deletions_now_allowed[i]
                next_event = deletions_now_allowed[i + 1]
                if (
                    current.filename != next_event.filename
                    and next_event.event_type != EventType.FILE_RENAMED
                    and current.timestamp
                    and next_event.timestamp
                ):
                    delta = (next_event.timestamp - current.timestamp).total_seconds()
                    if 0 < delta < 5:
                        rename_event = ForensicEvent(
                            timestamp=current.timestamp + timedelta(seconds=delta / 2),
                            event_type=EventType.FILE_RENAMED,
                            source=EventSource.CORRELATION,
                            filename=next_event.filename,
                            previous_filename=current.filename,
                            mft_reference=mft_ref,
                            confidence=Confidence.LOW.value,
                            notes=[
                                f"Inferred rename: {current.filename} → {next_event.filename}"
                            ],
                        )
                        events.append(rename_event)
                        logger.debug(
                            "Inferred rename: %s -> %s (MFT %d)",
                            current.filename, next_event.filename, mft_ref,
                        )
        return events

    @staticmethod
    def _deduplicate_events(
        events: list[ForensicEvent],
    ) -> list[ForensicEvent]:
        seen: set[tuple] = set()
        result: list[ForensicEvent] = []
        for e in events:
            key = (
                e.timestamp,
                e.event_type.value,
                e.mft_reference,
                e.filename,
                e.source.value,
            )
            if key not in seen:
                seen.add(key)
                result.append(e)
        return result

    def get_rename_chain(self, mft_reference: int) -> list[ForensicEvent]:
        return self._rename_chains.get(mft_reference, [])

    def get_file_history(self, mft_reference: int) -> list[ForensicEvent]:
        return self._file_history.get(mft_reference, [])

    def match_mft_usn(
        self,
        mft_events: list[ForensicEvent],
        usn_events: list[ForensicEvent],
        time_window_seconds: int = 5,
    ) -> list[ForensicEvent]:
        matched: list[ForensicEvent] = list(mft_events) + list(usn_events)
        for usn_e in usn_events:
            for mft_e in mft_events:
                if (
                    usn_e.mft_reference == mft_e.mft_reference
                    and usn_e.timestamp
                    and mft_e.timestamp
                ):
                    delta = abs((usn_e.timestamp - mft_e.timestamp).total_seconds())
                    if delta <= time_window_seconds:
                        usn_e.confidence = Confidence.HIGH.value
                        usn_e.notes.append(
                            f"Correlated with MFT event at {mft_e.timestamp}"
                        )
        return matched
