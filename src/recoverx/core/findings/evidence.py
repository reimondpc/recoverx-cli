from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvidenceLink:
    link_id: str
    description: str
    source: str = ""
    timestamp: str = ""
    confidence: float = 1.0
    related_mft: int = 0
    related_event: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.link_id,
            "description": self.description,
            "source": self.source,
            "timestamp": self.timestamp,
            "confidence": self.confidence,
            "mft_reference": self.related_mft,
            "event": self.related_event,
        }


@dataclass
class EvidenceChain:
    chain_id: str
    links: list[EvidenceLink] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_link(self, link: EvidenceLink) -> None:
        self.links.append(link)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chain_id": self.chain_id,
            "links": [l.to_dict() for l in self.links],
            "metadata": self.metadata,
            "total_links": len(self.links),
        }

    @property
    def average_confidence(self) -> float:
        if not self.links:
            return 0.0
        return sum(l.confidence for l in self.links) / len(self.links)
