from __future__ import annotations

from recoverx.core.forensics.models import EventType, ForensicEvent

from .base import AnalysisResult, BaseAnalyzer, FindingSeverity


class OrphanArtifactAnalyzer(BaseAnalyzer):
    def __init__(self) -> None:
        super().__init__("orphan_artifact")

    def analyze(self, events: list[ForensicEvent]) -> list[AnalysisResult]:
        results: list[AnalysisResult] = []
        all_mft = {e.mft_reference for e in events if e.mft_reference > 0}
        created_mft = {e.mft_reference for e in events if e.event_type == EventType.FILE_CREATED}
        deleted_mft = {
            e.mft_reference
            for e in events
            if e.event_type == EventType.FILE_DELETED and e.mft_reference > 0
        }

        orphans = all_mft - created_mft
        orphan_deletes = deleted_mft - created_mft

        if orphans:
            results.append(
                AnalysisResult(
                    analyzer_name=self._name,
                    severity=FindingSeverity.MEDIUM,
                    confidence=0.7,
                    description=f"Orphan artifacts: {len(orphans)} without create records",
                    evidence_refs=[f"MFT {m}" for m in list(orphans)[:20]],
                    mft_references=list(orphans),
                    event_count=len(orphans),
                    details={
                        "orphan_count": len(orphans),
                        "orphan_deletes": len(orphan_deletes),
                    },
                )
            )

        if orphan_deletes:
            results.append(
                AnalysisResult(
                    analyzer_name=self._name,
                    severity=FindingSeverity.HIGH,
                    confidence=0.85,
                    description=f"Orphan deletions: {len(orphan_deletes)} deletes without creates",
                    evidence_refs=[f"MFT {m}" for m in list(orphan_deletes)[:20]],
                    mft_references=list(orphan_deletes),
                    event_count=len(orphan_deletes),
                    details={
                        "orphan_delete_count": len(orphan_deletes),
                    },
                )
            )

        return self.filter_by_confidence(results)
