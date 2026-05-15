from __future__ import annotations

from recoverx.core.forensics.models import ForensicEvent

from .base import AnalysisResult, BaseAnalyzer, FindingSeverity


class TimestampAnomalyAnalyzer(BaseAnalyzer):
    def __init__(self, max_reversals_normal: int = 2) -> None:
        super().__init__("timestamp_anomaly")
        self._max_normal = max_reversals_normal

    def analyze(self, events: list[ForensicEvent]) -> list[AnalysisResult]:
        results: list[AnalysisResult] = []
        by_mft: dict[int, list[ForensicEvent]] = {}
        for e in events:
            if e.mft_reference > 0:
                by_mft.setdefault(e.mft_reference, []).append(e)

        total_reversals = 0
        reversal_details: list[str] = []

        for mft_ref, file_events in by_mft.items():
            for i in range(len(file_events) - 1):
                cur, nxt = file_events[i], file_events[i + 1]
                if cur.timestamp and nxt.timestamp and nxt.timestamp < cur.timestamp:
                    total_reversals += 1
                    reversal_details.append(
                        f"MFT {mft_ref}: {cur.filename} at {cur.timestamp} → " f"{nxt.timestamp}"
                    )

        if total_reversals == 0:
            return results

        severity = FindingSeverity.INFO
        confidence = 0.3
        if total_reversals > self._max_normal * 3:
            severity = FindingSeverity.HIGH
            confidence = 0.85
        elif total_reversals > self._max_normal * 2:
            severity = FindingSeverity.MEDIUM
            confidence = 0.65
        elif total_reversals > self._max_normal:
            severity = FindingSeverity.LOW
            confidence = 0.45

        results.append(
            AnalysisResult(
                analyzer_name=self._name,
                severity=severity,
                confidence=confidence,
                description=f"Timestamp anomalies: {total_reversals} reversals detected",
                evidence_refs=reversal_details[:10],
                mft_references=list(by_mft.keys()),
                event_count=total_reversals,
                details={"total_reversals": total_reversals, "examples": reversal_details[:5]},
            )
        )

        return self.filter_by_confidence(results)
