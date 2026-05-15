from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from recoverx.core.forensics.models import ForensicEvent


@dataclass
class CorrelationScore:
    mft_reference: int
    filename: str
    anomaly_score: float = 0.0
    heuristic_score: float = 0.0
    rename_score: float = 0.0
    delete_recreate_score: float = 0.0
    total_score: float = 0.0
    tags: list[str] = field(default_factory=list)

    def compute_total(self) -> float:
        self.total_score = (
            self.anomaly_score * 0.3
            + self.heuristic_score * 0.25
            + self.rename_score * 0.25
            + self.delete_recreate_score * 0.2
        )
        return self.total_score

    def severity_label(self) -> str:
        if self.total_score >= 0.8:
            return "critical"
        if self.total_score >= 0.6:
            return "high"
        if self.total_score >= 0.4:
            return "medium"
        if self.total_score >= 0.2:
            return "low"
        return "info"

    def to_dict(self) -> dict[str, Any]:
        return {
            "mft_reference": self.mft_reference,
            "filename": self.filename,
            "anomaly_score": round(self.anomaly_score, 3),
            "heuristic_score": round(self.heuristic_score, 3),
            "rename_score": round(self.rename_score, 3),
            "delete_recreate_score": round(self.delete_recreate_score, 3),
            "total_score": round(self.total_score, 3),
            "severity": self.severity_label(),
            "tags": self.tags,
        }


class CorrelationScorer:
    def __init__(self) -> None:
        self._scores: dict[int, CorrelationScore] = {}

    def score_event(self, event: ForensicEvent) -> CorrelationScore:
        mft = event.mft_reference
        if mft not in self._scores:
            self._scores[mft] = CorrelationScore(mft_reference=mft, filename=event.filename)
        return self._scores[mft]

    def score_anomaly(self, mft_ref: int, severity: float) -> None:
        if mft_ref in self._scores:
            self._scores[mft_ref].anomaly_score = max(self._scores[mft_ref].anomaly_score, severity)

    def score_heuristic(self, mft_ref: int, score: float) -> None:
        if mft_ref in self._scores:
            self._scores[mft_ref].heuristic_score = max(
                self._scores[mft_ref].heuristic_score, score
            )

    def score_rename(self, mft_ref: int, count: int) -> None:
        if mft_ref in self._scores:
            self._scores[mft_ref].rename_score = min(1.0, count / 10.0)

    def score_delete_recreate(self, mft_ref: int, cycles: int) -> None:
        if mft_ref in self._scores:
            self._scores[mft_ref].delete_recreate_score = min(1.0, cycles / 5.0)

    def finalize(self) -> list[CorrelationScore]:
        for score in self._scores.values():
            score.compute_total()
            if score.anomaly_score > 0.5:
                score.tags.append("anomaly")
            if score.heuristic_score > 0.5:
                score.tags.append("suspicious")
            if score.rename_score > 0.5:
                score.tags.append("frequent_rename")
            if score.delete_recreate_score > 0.5:
                score.tags.append("delete_recreate")
        return sorted(self._scores.values(), key=lambda x: x.total_score, reverse=True)

    def clear(self) -> None:
        self._scores.clear()
