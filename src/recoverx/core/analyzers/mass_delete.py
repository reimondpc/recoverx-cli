from __future__ import annotations

from collections import Counter

from recoverx.core.forensics.models import EventType, ForensicEvent

from .base import AnalysisResult, BaseAnalyzer, FindingSeverity


class MassDeleteAnalyzer(BaseAnalyzer):
    def __init__(self, threshold: int = 10, time_window_minutes: float = 60.0) -> None:
        super().__init__("mass_delete")
        self._threshold = threshold
        self._time_window = time_window_minutes

    def analyze(self, events: list[ForensicEvent]) -> list[AnalysisResult]:
        results: list[AnalysisResult] = []
        deletes = [e for e in events if e.event_type == EventType.FILE_DELETED]
        if len(deletes) < self._threshold:
            return results

        parent_counter: Counter[int] = Counter()
        name_counter: Counter[str] = Counter()
        for d in deletes:
            if d.parent_mft_reference:
                parent_counter[d.parent_mft_reference] += 1
            if d.filename:
                name_counter[d.filename] += 1

        severity = FindingSeverity.INFO
        confidence = 0.3
        if len(deletes) >= self._threshold * 5:
            severity = FindingSeverity.CRITICAL
            confidence = 0.95
        elif len(deletes) >= self._threshold * 3:
            severity = FindingSeverity.HIGH
            confidence = 0.8
        elif len(deletes) >= self._threshold:
            severity = FindingSeverity.MEDIUM
            confidence = 0.6

        top_parent = parent_counter.most_common(1)
        top_names = name_counter.most_common(5)

        results.append(
            AnalysisResult(
                analyzer_name=self._name,
                severity=severity,
                confidence=confidence,
                description=f"Mass deletion detected: {len(deletes)} files deleted",
                evidence_refs=[f"{name} ({count}x)" for name, count in top_names],
                mft_references=[p[0] for p in top_parent],
                event_count=len(deletes),
                details={
                    "total_deletes": len(deletes),
                    "top_parent": top_parent[0][0] if top_parent else 0,
                    "top_filenames": dict(top_names),
                },
            )
        )

        return self.filter_by_confidence(results)
