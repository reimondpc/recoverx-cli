from __future__ import annotations

from datetime import datetime

from recoverx.core.correlation.graph import CorrelationEdge, CorrelationGraph, CorrelationNode
from recoverx.core.forensics.models import EventSource, EventType, ForensicEvent


class TestCorrelationGraph:
    def _make_event(
        self,
        ts: datetime,
        etype: EventType,
        fname: str,
        mft: int = 1,
        source: EventSource = EventSource.MFT,
    ) -> ForensicEvent:
        return ForensicEvent(
            timestamp=ts,
            event_type=etype,
            source=source,
            filename=fname,
            mft_reference=mft,
        )

    def test_add_node(self):
        graph = CorrelationGraph()
        node = graph.add_node("n1", "Test Node", "test", mft_ref=1, filename="f.txt")
        assert isinstance(node, CorrelationNode)
        assert node.node_id == "n1"
        assert node.label == "Test Node"
        assert node.node_type == "test"
        assert node.mft_reference == 1
        assert node.filename == "f.txt"
        assert graph.node_count == 1

    def test_add_node_with_metadata(self):
        graph = CorrelationGraph()
        node = graph.add_node(
            "n_meta",
            "Meta Node",
            "meta",
            mft_ref=5,
            filename="meta.txt",
            metadata={"key": "val"},
        )
        assert node.metadata == {"key": "val"}

    def test_add_node_duplicate_overwrites(self):
        graph = CorrelationGraph()
        graph.add_node("dup", "First", "test")
        graph.add_node("dup", "Second", "test")
        assert graph.node_count == 1
        assert graph._nodes["dup"].label == "Second"

    def test_add_event_node(self):
        graph = CorrelationGraph()
        now = datetime.now()
        event = self._make_event(now, EventType.FILE_CREATED, "created.txt", mft=42)
        node = graph.add_event_node(event)
        assert isinstance(node, CorrelationNode)
        assert node.node_type == "event"
        assert node.mft_reference == 42
        assert node.filename == "created.txt"
        assert event.mft_reference == 42
        assert graph.node_count == 1

    def test_add_edge(self):
        graph = CorrelationGraph()
        graph.add_node("src", "Source", "event")
        graph.add_node("tgt", "Target", "event")
        edge = graph.add_edge("src", "tgt", "related", weight=0.8)
        assert isinstance(edge, CorrelationEdge)
        assert edge.source_id == "src"
        assert edge.target_id == "tgt"
        assert edge.edge_type == "related"
        assert edge.weight == 0.8
        assert graph.edge_count == 1

    def test_add_edge_with_metadata(self):
        graph = CorrelationGraph()
        graph.add_node("a", "A", "event")
        graph.add_node("b", "B", "event")
        edge = graph.add_edge("a", "b", "test", metadata={"info": "edge data"})
        assert edge.metadata == {"info": "edge data"}

    def test_add_edge_auto_id_increment(self):
        graph = CorrelationGraph()
        graph.add_node("a", "A", "event")
        graph.add_node("b", "B", "event")
        e1 = graph.add_edge("a", "b", "type1")
        e2 = graph.add_edge("a", "b", "type2")
        assert e1.edge_id != e2.edge_id

    def test_link_events(self):
        graph = CorrelationGraph()
        now = datetime.now()
        src = self._make_event(now, EventType.FILE_CREATED, "src.txt", mft=1)
        tgt = self._make_event(now, EventType.FILE_RENAMED, "tgt.txt", mft=2)
        edge = graph.link_events(src, tgt, "rename")
        assert isinstance(edge, CorrelationEdge)
        assert edge.edge_type == "rename"
        assert graph.node_count == 2
        assert graph.edge_count == 1

    def test_link_events_creates_nodes_automatically(self):
        graph = CorrelationGraph()
        now = datetime.now()
        a = self._make_event(now, EventType.FILE_CREATED, "a.txt", mft=10)
        b = self._make_event(now, EventType.FILE_MODIFIED, "a.txt", mft=20)
        graph.link_events(a, b, "modify")
        assert graph.node_count == 2

    def test_link_events_reuses_existing_node(self):
        graph = CorrelationGraph()
        now = datetime.now()
        a = self._make_event(now, EventType.FILE_CREATED, "a.txt", mft=10)
        b = self._make_event(now, EventType.FILE_MODIFIED, "a.txt", mft=20)
        graph.add_event_node(a)
        graph.link_events(a, b, "modify")
        assert graph.node_count == 2

    def test_traverse_from_bfs(self):
        graph = CorrelationGraph()
        graph.add_node("a", "A", "event")
        graph.add_node("b", "B", "event")
        graph.add_node("c", "C", "event")
        graph.add_edge("a", "b", "relation")
        graph.add_edge("b", "c", "relation")
        result = graph.traverse_from("a")
        ids = [n.node_id for n in result]
        assert "a" in ids
        assert "b" in ids
        assert "c" in ids

    def test_traverse_from_limited_by_max_depth(self):
        graph = CorrelationGraph()
        graph.add_node("a", "A", "event")
        graph.add_node("b", "B", "event")
        graph.add_node("c", "C", "event")
        graph.add_edge("a", "b", "rel")
        graph.add_edge("b", "c", "rel")
        result = graph.traverse_from("a", max_depth=2)
        assert len(result) <= 2

    def test_traverse_from_unknown_node_returns_empty(self):
        graph = CorrelationGraph()
        result = graph.traverse_from("nonexistent")
        assert result == []

    def test_traverse_from_no_edges_returns_self(self):
        graph = CorrelationGraph()
        graph.add_node("solo", "Solo", "event")
        result = graph.traverse_from("solo")
        assert len(result) == 1
        assert result[0].node_id == "solo"

    def test_find_path_between_nodes(self):
        graph = CorrelationGraph()
        graph.add_node("a", "A", "event")
        graph.add_node("b", "B", "event")
        graph.add_node("c", "C", "event")
        graph.add_edge("a", "b", "rel")
        graph.add_edge("b", "c", "rel")
        path = graph.find_path("a", "c")
        assert len(path) == 2
        assert path[0].source_id == "a"
        assert path[1].target_id == "c"

    def test_find_path_no_path_returns_empty(self):
        graph = CorrelationGraph()
        graph.add_node("a", "A", "event")
        graph.add_node("b", "B", "event")
        path = graph.find_path("a", "b")
        assert path == []

    def test_find_path_same_node(self):
        graph = CorrelationGraph()
        graph.add_node("a", "A", "event")
        path = graph.find_path("a", "a")
        assert path == []

    def test_to_dict_serialization(self):
        graph = CorrelationGraph()
        graph.add_node("n1", "Node 1", "event", mft_ref=1, filename="f1.txt")
        graph.add_node("n2", "Node 2", "event", mft_ref=2, filename="f2.txt")
        graph.add_edge("n1", "n2", "linked", weight=1.0)
        d = graph.to_dict()
        assert "nodes" in d
        assert "edges" in d
        assert len(d["nodes"]) == 2
        assert len(d["edges"]) == 1
        assert d["nodes"][0]["id"] == "n1"
        assert d["edges"][0]["type"] == "linked"

    def test_to_dict_node_structure(self):
        graph = CorrelationGraph()
        graph.add_node("x", "Label X", "custom", mft_ref=7, filename="x.txt")
        d = graph.to_dict()
        node = d["nodes"][0]
        assert node["id"] == "x"
        assert node["label"] == "Label X"
        assert node["type"] == "custom"
        assert node["mft_reference"] == 7
        assert node["filename"] == "x.txt"

    def test_to_dict_empty_graph(self):
        graph = CorrelationGraph()
        d = graph.to_dict()
        assert d == {"nodes": [], "edges": []}

    def test_node_count_property(self):
        graph = CorrelationGraph()
        assert graph.node_count == 0
        graph.add_node("a", "A", "event")
        assert graph.node_count == 1
        graph.add_node("b", "B", "event")
        assert graph.node_count == 2

    def test_edge_count_property(self):
        graph = CorrelationGraph()
        assert graph.edge_count == 0
        graph.add_node("a", "A", "event")
        graph.add_node("b", "B", "event")
        graph.add_edge("a", "b", "rel")
        assert graph.edge_count == 1
        graph.add_edge("b", "a", "rev")
        assert graph.edge_count == 2

    def test_clear_removes_all_nodes_and_edges(self):
        graph = CorrelationGraph()
        graph.add_node("a", "A", "event")
        graph.add_node("b", "B", "event")
        graph.add_edge("a", "b", "rel")
        assert graph.node_count == 2
        assert graph.edge_count == 1
        graph.clear()
        assert graph.node_count == 0
        assert graph.edge_count == 0

    def test_clear_resets_edge_counter(self):
        graph = CorrelationGraph()
        graph.add_node("a", "A", "event")
        graph.add_node("b", "B", "event")
        e1 = graph.add_edge("a", "b", "first")
        graph.clear()
        graph.add_node("a", "A", "event")
        graph.add_node("b", "B", "event")
        e2 = graph.add_edge("a", "b", "second")
        assert e1.edge_id == e2.edge_id
        assert e2.edge_id == "e_1"

    def test_empty_graph_node_count(self):
        graph = CorrelationGraph()
        assert graph.node_count == 0

    def test_empty_graph_edge_count(self):
        graph = CorrelationGraph()
        assert graph.edge_count == 0

    def test_empty_graph_traverse(self):
        graph = CorrelationGraph()
        assert graph.traverse_from("nope") == []

    def test_empty_graph_find_path(self):
        graph = CorrelationGraph()
        assert graph.find_path("x", "y") == []

    def test_traverse_from_undirected_edges(self):
        graph = CorrelationGraph()
        graph.add_node("a", "A", "event")
        graph.add_node("b", "B", "event")
        graph.add_node("c", "C", "event")
        graph.add_edge("a", "b", "rel")
        graph.add_edge("c", "b", "rel")
        result = graph.traverse_from("c")
        ids = {n.node_id for n in result}
        assert ids == {"c", "b", "a"}

    def test_multiple_edges_between_same_nodes(self):
        graph = CorrelationGraph()
        graph.add_node("a", "A", "event")
        graph.add_node("b", "B", "event")
        e1 = graph.add_edge("a", "b", "type_a")
        e2 = graph.add_edge("a", "b", "type_b")
        assert graph.edge_count == 2
        assert e1.edge_id != e2.edge_id
