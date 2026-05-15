from __future__ import annotations

import logging
from datetime import datetime, timedelta

from recoverx.core.forensics.models import Confidence, EventSource, EventType, ForensicEvent

logger = logging.getLogger("recoverx")


class CorrelationEngine:
    def __init__(self) -> None:
        self._rename_chains: dict[int, list[ForensicEvent]] = {}
        self._file_history: dict[int, list[ForensicEvent]] = {}
        self._delete_recreate: dict[int, list[ForensicEvent]] = {}
        self._parent_moves: dict[int, list[ForensicEvent]] = {}

    def correlate(self, events: list[ForensicEvent]) -> list[ForensicEvent]:
        correlated: list[ForensicEvent] = list(events)
        correlated = self._correlate_renames(correlated)
        correlated = self._detect_delete_recreate(correlated)
        correlated = self._track_parent_movement(correlated)
        correlated = self._detect_timestamp_anomalies(correlated)
        correlated = self._reconstruct_orphans(correlated)
        correlated = self._deduplicate_events(correlated)
        return correlated

    # ── Rename chain correlation ──────────────────────────────

    def _correlate_renames(self, events: list[ForensicEvent]) -> list[ForensicEvent]:
        by_mft: dict[int, list[ForensicEvent]] = {}
        for e in events:
            if e.mft_reference > 0:
                by_mft.setdefault(e.mft_reference, []).append(e)

        for mft_ref, file_events in by_mft.items():
            sorted_events = sorted(file_events, key=lambda x: x.timestamp or datetime.min)
            deletions_now_allowed = [
                e for e in sorted_events if e.event_type != EventType.FILE_DELETED
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
                            notes=[f"Inferred rename: {current.filename} -> {next_event.filename}"],
                        )
                        events.append(rename_event)
                        logger.debug(
                            "Inferred rename: %s -> %s (MFT %d)",
                            current.filename,
                            next_event.filename,
                            mft_ref,
                        )
        return events

    # ── Delete / Recreate detection ───────────────────────────

    def _detect_delete_recreate(self, events: list[ForensicEvent]) -> list[ForensicEvent]:
        by_mft: dict[int, list[ForensicEvent]] = {}
        for e in events:
            if e.mft_reference > 0:
                by_mft.setdefault(e.mft_reference, []).append(e)

        for mft_ref, file_events in by_mft.items():
            sorted_events = sorted(file_events, key=lambda x: x.timestamp or datetime.min)
            deletes = [e for e in sorted_events if e.event_type == EventType.FILE_DELETED]
            creates = [e for e in sorted_events if e.event_type == EventType.FILE_CREATED]

            for d in deletes:
                if not d.timestamp:
                    continue
                for c in creates:
                    if not c.timestamp:
                        continue
                    delta = (c.timestamp - d.timestamp).total_seconds()
                    if 0 < delta < 60 and c.filename == d.filename:
                        note = (
                            f"Delete/recreate detected: {d.filename}"
                            f" deleted then recreated ({delta:.0f}s gap)"
                        )
                        c.notes.append(note)
                        d.notes.append(note)
                        self._delete_recreate.setdefault(mft_ref, []).extend([d, c])
                        logger.debug(
                            "Delete/recreate: %s (MFT %d, gap %.0fs)", d.filename, mft_ref, delta
                        )

        return events

    # ── Parent movement tracking ──────────────────────────────

    def _track_parent_movement(self, events: list[ForensicEvent]) -> list[ForensicEvent]:
        by_mft: dict[int, list[ForensicEvent]] = {}
        for e in events:
            if e.mft_reference > 0:
                by_mft.setdefault(e.mft_reference, []).append(e)

        for mft_ref, file_events in by_mft.items():
            sorted_events = sorted(file_events, key=lambda x: x.timestamp or datetime.min)
            prev_parent = 0
            for e in sorted_events:
                if e.parent_mft_reference != 0 and e.parent_mft_reference != prev_parent:
                    if prev_parent != 0:
                        note = (
                            f"Parent moved: {e.filename}"
                            f" from {prev_parent} to {e.parent_mft_reference}"
                        )
                        e.notes.append(note)
                        self._parent_moves.setdefault(mft_ref, []).append(e)
                    prev_parent = e.parent_mft_reference

        return events

    # ── Timestamp anomaly detection ───────────────────────────

    @staticmethod
    def _detect_timestamp_anomalies(events: list[ForensicEvent]) -> list[ForensicEvent]:
        by_mft: dict[int, list[ForensicEvent]] = {}
        for e in events:
            if e.mft_reference > 0:
                by_mft.setdefault(e.mft_reference, []).append(e)

        for mft_ref, file_events in by_mft.items():
            for i in range(len(file_events) - 1):
                current = file_events[i]
                next_event = file_events[i + 1]
                if current.timestamp and next_event.timestamp:
                    delta = (next_event.timestamp - current.timestamp).total_seconds()
                    if delta < 0:
                        next_event.notes.append(
                            f"Anomalous timestamp"
                            f" ({next_event.timestamp} before {current.timestamp})"
                        )
                    elif delta == 0 and current.event_type != next_event.event_type:
                        next_event.notes.append("Zero-delta event burst detected")

        return events

    # ── Orphan reconstruction ─────────────────────────────────

    def _reconstruct_orphans(self, events: list[ForensicEvent]) -> list[ForensicEvent]:
        all_mft_refs = {e.mft_reference for e in events if e.mft_reference > 0}
        created_mft = {e.mft_reference for e in events if e.event_type == EventType.FILE_CREATED}
        deleted_mft = {e.mft_reference for e in events if e.event_type == EventType.FILE_DELETED}

        orphan_refs = all_mft_refs - created_mft
        for mft_ref in orphan_refs:
            for e in events:
                if e.mft_reference == mft_ref and "orphan" not in " ".join(e.notes).lower():
                    e.notes.append("Orphan event: no creation record found")

        for mft_ref in deleted_mft - created_mft:
            for e in events:
                if e.mft_reference == mft_ref and e.event_type == EventType.FILE_DELETED:
                    e.notes.append("Orphan deletion: no matching creation record")

        return events

    # ── Cross-source matching ─────────────────────────────────

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
                        usn_e.notes.append(f"Correlated with MFT event at {mft_e.timestamp}")
                        self._storage_correlation(
                            "mft_usn", usn_e.mft_reference, mft_e.mft_reference, delta
                        )
        return matched

    def _storage_correlation(self, corr_type: str, id_a: int, id_b: int, delta: float) -> None:
        pass

    @staticmethod
    def _deduplicate_events(events: list[ForensicEvent]) -> list[ForensicEvent]:
        seen: set[tuple] = set()
        result: list[ForensicEvent] = []
        for e in events:
            key = (e.timestamp, e.event_type.value, e.mft_reference, e.filename, e.source.value)
            if key not in seen:
                seen.add(key)
                result.append(e)
        return result

    # ── Accessors ─────────────────────────────────────────────

    def get_rename_chain(self, mft_reference: int) -> list[ForensicEvent]:
        return self._rename_chains.get(mft_reference, [])

    def get_file_history(self, mft_reference: int) -> list[ForensicEvent]:
        return self._file_history.get(mft_reference, [])

    def get_delete_recreate(self, mft_reference: int) -> list[ForensicEvent]:
        return self._delete_recreate.get(mft_reference, [])

    def get_parent_moves(self, mft_reference: int) -> list[ForensicEvent]:
        return self._parent_moves.get(mft_reference, [])
