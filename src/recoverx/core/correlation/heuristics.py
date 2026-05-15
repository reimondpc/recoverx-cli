from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from recoverx.core.forensics.models import EventType, ForensicEvent


class HeuristicType(Enum):
    SUSPICIOUS_RENAME = auto()
    MASS_DELETE = auto()
    OVERWRITE_PATTERN = auto()
    ORPHAN_ACTIVITY = auto()
    DUPLICATE_EVENTS = auto()
    UNUSUAL_TIMING = auto()


@dataclass
class HeuristicResult:
    heuristic_type: HeuristicType
    score: float
    description: str
    evidence: list[str] = field(default_factory=list)
    mft_references: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.heuristic_type.name,
            "score": self.score,
            "description": self.description,
            "evidence": self.evidence,
            "mft_references": self.mft_references,
        }


class HeuristicRule:
    def __init__(self, name: str, weight: float = 1.0) -> None:
        self.name = name
        self.weight = weight

    def evaluate(self, events: list[ForensicEvent]) -> HeuristicResult | None:
        raise NotImplementedError


class MassDeleteRule(HeuristicRule):
    def __init__(self, threshold: int = 10, time_window: float = 60.0) -> None:
        super().__init__("mass_delete")
        self._threshold = threshold
        self._time_window = time_window

    def evaluate(self, events: list[ForensicEvent]) -> HeuristicResult | None:
        deletes = [e for e in events if e.event_type == EventType.FILE_DELETED]
        if len(deletes) >= self._threshold:
            return HeuristicResult(
                heuristic_type=HeuristicType.MASS_DELETE,
                score=min(1.0, len(deletes) / (self._threshold * 2)),
                description=f"Mass delete detected: {len(deletes)} deletions",
                evidence=[f"{e.filename} deleted" for e in deletes[:10]],
                mft_references=[e.mft_reference for e in deletes[:10]],
            )
        return None


class SuspiciousRenameRule(HeuristicRule):
    def __init__(self, threshold: int = 5) -> None:
        super().__init__("suspicious_rename")
        self._threshold = threshold

    def evaluate(self, events: list[ForensicEvent]) -> HeuristicResult | None:
        renames = [e for e in events if e.event_type == EventType.FILE_RENAMED]
        if len(renames) >= self._threshold:
            return HeuristicResult(
                heuristic_type=HeuristicType.SUSPICIOUS_RENAME,
                score=min(1.0, len(renames) / (self._threshold * 2)),
                description=f"Suspicious rename activity: {len(renames)} renames",
                evidence=[f"{e.previous_filename} -> {e.filename}" for e in renames[:10]],
                mft_references=[e.mft_reference for e in renames[:10]],
            )
        return None


class HeuristicEngine:
    def __init__(self) -> None:
        self._rules: list[HeuristicRule] = [
            MassDeleteRule(),
            SuspiciousRenameRule(),
        ]

    def add_rule(self, rule: HeuristicRule) -> None:
        self._rules.append(rule)

    def analyze(self, events: list[ForensicEvent]) -> list[HeuristicResult]:
        results: list[HeuristicResult] = []
        for rule in self._rules:
            try:
                result = rule.evaluate(events)
                if result:
                    results.append(result)
            except Exception:
                continue
        return results
