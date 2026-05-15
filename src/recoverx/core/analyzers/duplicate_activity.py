from __future__ import annotations

from collections import Counter

from recoverx.core.forensics.models import ForensicEvent

from .base import AnalysisResult, BaseAnalyzer, FindingSeverity


class DuplicateActivityAnalyzer(BaseAnalyzer):
    def __init__(self, threshold: int = 5) -> None:
        super().__init__("duplicate_activity")
        self._threshold = threshold

    def analyze(self, events: list[ForensicEvent]) -> list[AnalysisResult]:
        results: list[AnalysisResult] = []
        event_key: Counter[tuple[str, str, int]] = Counter()
        for e in events:
            key = (e.event_type.name, e.filename, e.mft_reference)
            event_key[key] += 1

        duplicates = {k: v for k, v in event_key.items() if v >= self._threshold}
        if not duplicates:
            return results

        total_duplicates = sum(duplicates.values())
        severity = FindingSeverity.INFO
        confidence = 0.3
        if total_duplicates >= self._threshold * 5:
            severity = FindingSeverity.HIGH
            confidence = 0.8
        elif total_duplicates >= self._threshold * 3:
            severity = FindingSeverity.MEDIUM
            confidence = 0.6
        elif total_duplicates >= self._threshold:
            severity = FindingSeverity.LOW
            confidence = 0.4

        evidence = [
            f"{etype} {fname} (MFT {mft}): {count}x"
            for (etype, fname, mft), count in list(duplicates.items())[:10]
        ]

        results.append(
            AnalysisResult(
                analyzer_name=self._name,
                severity=severity,
                confidence=confidence,
                description=f"Duplicate activity: {len(duplicates)} repeating events ({total_duplicates} total)",
                evidence_refs=evidence,
                mft_references=list(set(mft for _, _, mft in duplicates)),
                event_count=total_duplicates,
                details={"duplicate_groups": len(duplicates), "total_duplicates": total_duplicates},
            )
        )

        return self.filter_by_confidence(results)
