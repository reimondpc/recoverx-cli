from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any

from recoverx.core.forensics.models import ForensicEvent


class AnomalyType(Enum):
    TIMESTAMP_REVERSAL = auto()
    ZERO_DELTA_BURST = auto()
    MISSING_CREATE = auto()
    MISSING_DELETE = auto()
    RAPID_RENAME = auto()
    LARGE_GAP = auto()
    OUT_OF_ORDER = auto()
    INTERLEAVED_ACTIVITY = auto()


@dataclass
class AnomalyScore:
    anomaly_type: AnomalyType
    severity: float
    description: str
    mft_reference: int = 0
    filename: str = ""
    related_events: list[ForensicEvent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.anomaly_type.name,
            "severity": self.severity,
            "description": self.description,
            "mft_reference": self.mft_reference,
            "filename": self.filename,
        }


class AnomalyDetector:
    def __init__(self, time_window_seconds: float = 5.0) -> None:
        self._time_window = time_window_seconds

    def detect(self, events: list[ForensicEvent]) -> list[AnomalyScore]:
        scores: list[AnomalyScore] = []
        scores.extend(self._detect_timestamp_reversals(events))
        scores.extend(self._detect_zero_delta_bursts(events))
        scores.extend(self._detect_rapid_renames(events))
        scores.extend(self._detect_interleaved_activity(events))
        return scores

    def _detect_timestamp_reversals(self, events: list[ForensicEvent]) -> list[AnomalyScore]:
        scores: list[AnomalyScore] = []
        by_mft: dict[int, list[ForensicEvent]] = {}
        for e in events:
            if e.mft_reference > 0:
                by_mft.setdefault(e.mft_reference, []).append(e)
        for mft_ref, file_events in by_mft.items():
            for i in range(len(file_events) - 1):
                cur, nxt = file_events[i], file_events[i + 1]
                if cur.timestamp and nxt.timestamp and nxt.timestamp < cur.timestamp:
                    scores.append(
                        AnomalyScore(
                            anomaly_type=AnomalyType.TIMESTAMP_REVERSAL,
                            severity=0.8,
                            description=f"Timestamp reversal: {nxt.timestamp} before {cur.timestamp}",
                            mft_reference=mft_ref,
                            filename=cur.filename,
                            related_events=[cur, nxt],
                        )
                    )
        return scores

    def _detect_zero_delta_bursts(self, events: list[ForensicEvent]) -> list[AnomalyScore]:
        scores: list[AnomalyScore] = []
        by_mft: dict[int, list[ForensicEvent]] = {}
        for e in events:
            if e.mft_reference > 0:
                by_mft.setdefault(e.mft_reference, []).append(e)
        for mft_ref, file_events in by_mft.items():
            for i in range(len(file_events) - 2):
                a, b, c = file_events[i], file_events[i + 1], file_events[i + 2]
                if a.timestamp and b.timestamp and c.timestamp:
                    d1 = (b.timestamp - a.timestamp).total_seconds()
                    d2 = (c.timestamp - b.timestamp).total_seconds()
                    if d1 == 0 and d2 == 0:
                        scores.append(
                            AnomalyScore(
                                anomaly_type=AnomalyType.ZERO_DELTA_BURST,
                                severity=0.6,
                                description="Three+ events with identical timestamps",
                                mft_reference=mft_ref,
                                filename=a.filename,
                            )
                        )
        return scores

    def _detect_rapid_renames(self, events: list[ForensicEvent]) -> list[AnomalyScore]:
        scores: list[AnomalyScore] = []
        renames = [e for e in events if e.event_type.name == "FILE_RENAMED"]
        for i in range(len(renames) - 1):
            a, b = renames[i], renames[i + 1]
            if a.mft_reference == b.mft_reference and a.timestamp and b.timestamp:
                delta = (b.timestamp - a.timestamp).total_seconds()
                if 0 < delta < self._time_window:
                    scores.append(
                        AnomalyScore(
                            anomaly_type=AnomalyType.RAPID_RENAME,
                            severity=0.7,
                            description=f"Rapid rename: {delta:.1f}s gap",
                            mft_reference=a.mft_reference,
                            filename=a.filename,
                            related_events=[a, b],
                        )
                    )
        return scores

    def _detect_interleaved_activity(self, events: list[ForensicEvent]) -> list[AnomalyScore]:
        scores: list[AnomalyScore] = []
        by_mft: dict[int, list[ForensicEvent]] = {}
        for e in events:
            if e.mft_reference > 0:
                by_mft.setdefault(e.mft_reference, []).append(e)
        _ = self._time_window
        for mft_ref, file_events in by_mft.items():
            sources = set(e.source.name for e in file_events)
            if len(sources) > 1:
                scores.append(
                    AnomalyScore(
                        anomaly_type=AnomalyType.INTERLEAVED_ACTIVITY,
                        severity=0.4,
                        description=f"Activity from multiple sources: {', '.join(sorted(sources))}",
                        mft_reference=mft_ref,
                        filename=file_events[0].filename,
                    )
                )
        return scores
