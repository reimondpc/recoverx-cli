from __future__ import annotations

import logging
from typing import Any

from recoverx.core.forensics.models import ForensicEvent

from .anomalies import AnomalyDetector, AnomalyScore
from .chains import ChainBuilder, DeleteRecreateChain, RenameChain
from .graph import CorrelationGraph
from .heuristics import HeuristicEngine, HeuristicResult
from .scoring import CorrelationScore, CorrelationScorer

logger = logging.getLogger("recoverx")


class CorrelationEngineV2:
    def __init__(self) -> None:
        self._chain_builder = ChainBuilder()
        self._anomaly_detector = AnomalyDetector()
        self._heuristic_engine = HeuristicEngine()
        self._scorer = CorrelationScorer()
        self._graph = CorrelationGraph()

    @property
    def graph(self) -> CorrelationGraph:
        return self._graph

    @property
    def chain_builder(self) -> ChainBuilder:
        return self._chain_builder

    def analyze(self, events: list[ForensicEvent]) -> dict[str, Any]:
        rename_chains = self._chain_builder.build_rename_chains(events)
        delete_recreate = self._chain_builder.build_delete_recreate(events)
        anomalies = self._anomaly_detector.detect(events)
        heuristics = self._heuristic_engine.analyze(events)

        for e in events:
            self._scorer.score_event(e)

        for a in anomalies:
            self._scorer.score_anomaly(a.mft_reference, a.severity)

        for h in heuristics:
            for mft_ref in h.mft_references:
                self._scorer.score_heuristic(mft_ref, h.score)

        for chain in rename_chains:
            self._scorer.score_rename(chain.mft_reference, chain.rename_count)

        for dr in delete_recreate:
            self._scorer.score_delete_recreate(dr.mft_reference, dr.cycle_count)

        self._build_graph(events, rename_chains, delete_recreate)

        scores = self._scorer.finalize()

        return {
            "rename_chains": [c.to_dict() for c in rename_chains],
            "delete_recreate": [d.to_dict() for d in delete_recreate],
            "anomalies": [a.to_dict() for a in anomalies],
            "heuristics": [h.to_dict() for h in heuristics],
            "scores": [s.to_dict() for s in scores],
            "graph": self._graph.to_dict(),
            "summary": self._summary(rename_chains, delete_recreate, anomalies, heuristics, scores),
        }

    def _build_graph(
        self,
        events: list[ForensicEvent],
        rename_chains: list[RenameChain],
        delete_recreate: list[DeleteRecreateChain],
    ) -> None:
        self._graph.clear()
        for event in events:
            self._graph.add_event_node(event)
        for chain in rename_chains:
            for i in range(len(chain.events) - 1):
                self._graph.link_events(chain.events[i], chain.events[i + 1], "rename")
        for dr in delete_recreate:
            for d in dr.deletes:
                for c in dr.creates:
                    self._graph.link_events(d, c, "delete_recreate")

    def _summary(
        self,
        rename_chains: list[RenameChain],
        delete_recreate: list[DeleteRecreateChain],
        anomalies: list[AnomalyScore],
        heuristics: list[HeuristicResult],
        scores: list[CorrelationScore],
    ) -> dict[str, Any]:
        return {
            "rename_chains": len(rename_chains),
            "delete_recreate_chains": len(delete_recreate),
            "anomalies": len(anomalies),
            "heuristic_findings": len(heuristics),
            "scored_artifacts": len(scores),
            "graph_nodes": self._graph.node_count,
            "graph_edges": self._graph.edge_count,
            "critical_findings": sum(1 for s in scores if s.severity_label() == "critical"),
            "high_findings": sum(1 for s in scores if s.severity_label() == "high"),
        }

    def clear(self) -> None:
        self._chain_builder = ChainBuilder()
        self._scorer.clear()
        self._graph.clear()
