from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from recoverx.core.forensics.models import ForensicEvent


@dataclass
class CorrelationNode:
    node_id: str
    label: str
    node_type: str
    mft_reference: int = 0
    filename: str = ""
    timestamp: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.node_id,
            "label": self.label,
            "type": self.node_type,
            "mft_reference": self.mft_reference,
            "filename": self.filename,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class CorrelationEdge:
    edge_id: str
    source_id: str
    target_id: str
    edge_type: str
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.edge_id,
            "source": self.source_id,
            "target": self.target_id,
            "type": self.edge_type,
            "weight": self.weight,
            "metadata": self.metadata,
        }


class CorrelationGraph:
    def __init__(self) -> None:
        self._nodes: dict[str, CorrelationNode] = {}
        self._edges: dict[str, CorrelationEdge] = {}
        self._edge_counter = 0

    def add_node(
        self,
        node_id: str,
        label: str,
        node_type: str,
        mft_ref: int = 0,
        filename: str = "",
        timestamp: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> CorrelationNode:
        node = CorrelationNode(
            node_id=node_id,
            label=label,
            node_type=node_type,
            mft_reference=mft_ref,
            filename=filename,
            timestamp=timestamp,
            metadata=metadata or {},
        )
        self._nodes[node_id] = node
        return node

    def add_event_node(self, event: ForensicEvent) -> CorrelationNode:
        node_id = f"event_{event.mft_reference}_{event.timestamp}"
        return self.add_node(
            node_id=node_id,
            label=f"{event.event_type.name}: {event.filename}",
            node_type="event",
            mft_ref=event.mft_reference,
            filename=event.filename,
            timestamp=event.timestamp.isoformat() if event.timestamp else "",
        )

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        weight: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> CorrelationEdge:
        self._edge_counter += 1
        edge_id = f"e_{self._edge_counter}"
        edge = CorrelationEdge(
            edge_id=edge_id,
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            weight=weight,
            metadata=metadata or {},
        )
        self._edges[edge_id] = edge
        return edge

    def link_events(
        self, source: ForensicEvent, target: ForensicEvent, rel_type: str
    ) -> CorrelationEdge:
        src_id = f"event_{source.mft_reference}_{source.timestamp}"
        tgt_id = f"event_{target.mft_reference}_{target.timestamp}"
        if src_id not in self._nodes:
            self.add_event_node(source)
        if tgt_id not in self._nodes:
            self.add_event_node(target)
        return self.add_edge(src_id, tgt_id, rel_type)

    def traverse_from(self, node_id: str, max_depth: int = 10) -> list[CorrelationNode]:
        visited: set[str] = set()
        result: list[CorrelationNode] = []
        queue = [(node_id, 0)]
        while queue and len(result) < max_depth:
            current, depth = queue.pop(0)
            if current in visited or depth > max_depth:
                continue
            visited.add(current)
            node = self._nodes.get(current)
            if node:
                result.append(node)
            for edge in self._edges.values():
                neighbor: str | None = None
                if edge.source_id == current:
                    neighbor = edge.target_id
                elif edge.target_id == current:
                    neighbor = edge.source_id
                if neighbor and neighbor not in visited:
                    queue.append((neighbor, depth + 1))
        return result

    def find_path(self, from_id: str, to_id: str) -> list[CorrelationEdge]:
        visited: set[str] = set()
        queue: list[tuple[str, list[CorrelationEdge]]] = [(from_id, [])]
        while queue:
            current, path = queue.pop(0)
            if current == to_id:
                return path
            if current in visited:
                continue
            visited.add(current)
            for edge in self._edges.values():
                if edge.source_id == current and edge.target_id not in visited:
                    queue.append((edge.target_id, path + [edge]))
                elif edge.target_id == current and edge.source_id not in visited:
                    queue.append((edge.source_id, path + [edge]))
        return []

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "edges": [e.to_dict() for e in self._edges.values()],
        }

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    def clear(self) -> None:
        self._nodes.clear()
        self._edges.clear()
        self._edge_counter = 0
