from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from recoverx.core.forensics.models import ForensicEvent


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

    @classmethod
    def from_score(cls, score: float) -> FindingSeverity:
        if score >= 0.8:
            return cls.CRITICAL
        if score >= 0.6:
            return cls.HIGH
        if score >= 0.4:
            return cls.MEDIUM
        if score >= 0.2:
            return cls.LOW
        return cls.INFO


@dataclass
class AnalysisResult:
    analyzer_name: str
    severity: FindingSeverity
    confidence: float
    description: str
    evidence_refs: list[str] = field(default_factory=list)
    mft_references: list[int] = field(default_factory=list)
    event_count: int = 0
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "analyzer": self.analyzer_name,
            "severity": self.severity.name,
            "severity_score": self.severity.score(),
            "confidence": self.confidence,
            "description": self.description,
            "evidence": self.evidence_refs,
            "mft_references": self.mft_references,
            "event_count": self.event_count,
            "details": self.details,
        }


class BaseAnalyzer(ABC):
    def __init__(self, name: str, min_confidence: float = 0.1) -> None:
        self._name = name
        self._min_confidence = min_confidence

    @property
    def name(self) -> str:
        return self._name

    @abstractmethod
    def analyze(self, events: list[ForensicEvent]) -> list[AnalysisResult]: ...

    def filter_by_confidence(self, results: list[AnalysisResult]) -> list[AnalysisResult]:
        return [r for r in results if r.confidence >= self._min_confidence]
