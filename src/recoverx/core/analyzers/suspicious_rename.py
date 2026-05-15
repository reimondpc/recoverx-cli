from __future__ import annotations

from recoverx.core.forensics.models import EventType, ForensicEvent

from .base import AnalysisResult, BaseAnalyzer, FindingSeverity


class SuspiciousRenameAnalyzer(BaseAnalyzer):
    def __init__(
        self,
        rapid_rename_threshold: float = 5.0,
        max_renames_normal: int = 3,
    ) -> None:
        super().__init__("suspicious_rename")
        self._rapid_threshold = rapid_rename_threshold
        self._max_normal = max_renames_normal

    def analyze(self, events: list[ForensicEvent]) -> list[AnalysisResult]:
        results: list[AnalysisResult] = []
        by_mft: dict[int, list[ForensicEvent]] = {}
        for e in events:
            if e.mft_reference > 0:
                by_mft.setdefault(e.mft_reference, []).append(e)

        for mft_ref, file_events in by_mft.items():
            renames = [e for e in file_events if e.event_type == EventType.FILE_RENAMED]
            if not renames:
                continue

            chain = " -> ".join(f"{r.previous_filename or '?'}→{r.filename}" for r in renames)
            total_renames = len(renames)
            rapid = 0
            for i in range(len(renames) - 1):
                a, b = renames[i], renames[i + 1]
                if a.timestamp and b.timestamp:
                    delta = (b.timestamp - a.timestamp).total_seconds()
                    if 0 < delta < self._rapid_threshold:
                        rapid += 1

            severity = FindingSeverity.LOW
            confidence = 0.3
            if total_renames > self._max_normal * 3:
                severity = FindingSeverity.HIGH
                confidence = 0.8
            elif total_renames > self._max_normal * 2:
                severity = FindingSeverity.MEDIUM
                confidence = 0.6
            elif total_renames > self._max_normal:
                severity = FindingSeverity.LOW
                confidence = 0.4

            if rapid > 1:
                confidence = min(1.0, confidence + 0.2)
                if severity == FindingSeverity.LOW:
                    severity = FindingSeverity.MEDIUM

            results.append(
                AnalysisResult(
                    analyzer_name=self._name,
                    severity=severity,
                    confidence=confidence,
                    description=f"Suspicious rename activity: {total_renames} renames, {rapid} rapid",
                    evidence_refs=[chain],
                    mft_references=[mft_ref],
                    event_count=total_renames,
                    details={"rename_chain": chain, "rapid_renames": rapid},
                )
            )

        return self.filter_by_confidence(results)
