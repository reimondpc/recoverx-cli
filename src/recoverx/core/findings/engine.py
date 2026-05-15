from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any

from recoverx.core.analyzers import AnalysisResult, BaseAnalyzer
from recoverx.core.forensics.models import ForensicEvent

from .evidence import EvidenceChain, EvidenceLink


class FindingSeverity(Enum):
    INFO = auto()
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    CRITICAL = auto()

    def score(self) -> float:
        return {
            FindingSeverity.INFO: 0.1,
            FindingSeverity.LOW: 0.3,
            FindingSeverity.MEDIUM: 0.5,
            FindingSeverity.HIGH: 0.7,
            FindingSeverity.CRITICAL: 0.9,
        }[self]


class FindingCategory(Enum):
    SUSPICIOUS_ACTIVITY = auto()
    ANTI_FORENSICS = auto()
    TIMESTAMP_TAMPERING = auto()
    BULK_DELETION = auto()
    OVERWRITE_PATTERN = auto()
    FRAGMENTED_ANOMALY = auto()
    ORPHAN_ACTIVITY = auto()
    DUPLICATE_ACTIVITY = auto()


@dataclass
class Finding:
    finding_id: str
    category: FindingCategory
    severity: FindingSeverity
    confidence: float
    title: str
    description: str
    evidence_chain: EvidenceChain | None = None
    related_artifacts: list[str] = field(default_factory=list)
    mft_references: list[int] = field(default_factory=list)
    timestamp: str = ""
    analyst_notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.finding_id,
            "category": self.category.name,
            "severity": self.severity.name,
            "severity_score": self.severity.score(),
            "confidence": self.confidence,
            "title": self.title,
            "description": self.description,
            "evidence": self.evidence_chain.to_dict() if self.evidence_chain else None,
            "related_artifacts": self.related_artifacts,
            "mft_references": self.mft_references,
            "timestamp": self.timestamp,
            "analyst_notes": self.analyst_notes,
        }

    @property
    def composite_score(self) -> float:
        return self.severity.score() * self.confidence


class FindingsEngine:
    def __init__(self) -> None:
        self._findings: dict[str, Finding] = {}
        self._analyzers: list[BaseAnalyzer] = []

    def register_analyzer(self, analyzer: BaseAnalyzer) -> None:
        self._analyzers.append(analyzer)

    def analyze(self, events: list[ForensicEvent]) -> list[Finding]:
        new_findings: list[Finding] = []
        for analyzer in self._analyzers:
            try:
                results = analyzer.analyze(events)
                for ar in results:
                    finding = self._result_to_finding(ar)
                    self._findings[finding.finding_id] = finding
                    new_findings.append(finding)
            except Exception:
                continue
        return new_findings

    def _result_to_finding(self, result: AnalysisResult) -> Finding:
        import uuid

        category = self._map_category(result.analyzer_name)
        chain = EvidenceChain(
            chain_id=uuid.uuid4().hex[:16],
            links=[
                EvidenceLink(
                    link_id=uuid.uuid4().hex[:8],
                    description=ref,
                    source="analyzer",
                )
                for ref in result.evidence_refs
            ],
        )
        return Finding(
            finding_id=uuid.uuid4().hex[:16],
            category=category,
            severity=self._map_severity(result.severity),
            confidence=result.confidence,
            title=result.description[:80],
            description=result.description,
            evidence_chain=chain,
            mft_references=result.mft_references,
            related_artifacts=result.evidence_refs,
            timestamp=datetime.now().isoformat(),
        )

    def _map_category(self, analyzer_name: str) -> FindingCategory:
        mapping = {
            "suspicious_rename": FindingCategory.SUSPICIOUS_ACTIVITY,
            "mass_delete": FindingCategory.BULK_DELETION,
            "timestamp_anomaly": FindingCategory.TIMESTAMP_TAMPERING,
            "duplicate_activity": FindingCategory.DUPLICATE_ACTIVITY,
            "orphan_artifact": FindingCategory.ORPHAN_ACTIVITY,
        }
        return mapping.get(analyzer_name, FindingCategory.SUSPICIOUS_ACTIVITY)

    def _map_severity(self, severity: Any) -> FindingSeverity:
        mapping = {
            "INFO": FindingSeverity.INFO,
            "LOW": FindingSeverity.LOW,
            "MEDIUM": FindingSeverity.MEDIUM,
            "HIGH": FindingSeverity.HIGH,
            "CRITICAL": FindingSeverity.CRITICAL,
        }
        return mapping.get(severity.name, FindingSeverity.INFO)

    def get_findings(
        self,
        min_severity: FindingSeverity | None = None,
        category: FindingCategory | None = None,
    ) -> list[Finding]:
        results = list(self._findings.values())
        if min_severity:
            results = [f for f in results if f.severity.score() >= min_severity.score()]
        if category:
            results = [f for f in results if f.category == category]
        return sorted(results, key=lambda f: f.composite_score, reverse=True)

    def summary(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for f in self._findings.values():
            counts[f.severity.name] = counts.get(f.severity.name, 0) + 1
        return {
            "total_findings": len(self._findings),
            "by_severity": counts,
            "categories": len(set(f.category for f in self._findings.values())),
        }

    def clear(self) -> None:
        self._findings.clear()
