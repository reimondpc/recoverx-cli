from __future__ import annotations

from datetime import datetime, timedelta

from recoverx.core.correlation.chains import DeleteRecreateChain, OverwriteChain, RenameChain
from recoverx.core.correlation.engine import CorrelationEngineV2
from recoverx.core.forensics.models import EventSource, EventType, ForensicEvent


class TestCorrelationEngineV2:
    def _make_event(
        self,
        ts: datetime,
        etype: EventType,
        fname: str,
        mft: int = 1,
        parent: int = 0,
        source: EventSource = EventSource.MFT,
        prev_fname: str = "",
    ) -> ForensicEvent:
        return ForensicEvent(
            timestamp=ts,
            event_type=etype,
            source=source,
            filename=fname,
            mft_reference=mft,
            parent_mft_reference=parent,
            previous_filename=prev_fname,
        )

    def test_analyze_returns_correct_dict_keys(self):
        engine = CorrelationEngineV2()
        now = datetime.now()
        events = [
            self._make_event(now, EventType.FILE_CREATED, "test.txt", mft=1),
        ]
        result = engine.analyze(events)
        assert isinstance(result, dict)
        assert "rename_chains" in result
        assert "delete_recreate" in result
        assert "anomalies" in result
        assert "heuristics" in result
        assert "scores" in result
        assert "graph" in result
        assert "summary" in result

    def test_analyze_empty_events_list(self):
        engine = CorrelationEngineV2()
        result = engine.analyze([])
        assert result["rename_chains"] == []
        assert result["delete_recreate"] == []
        assert result["anomalies"] == []
        assert result["heuristics"] == []
        assert result["scores"] == []
        assert result["summary"]["rename_chains"] == 0
        assert result["summary"]["delete_recreate_chains"] == 0
        assert result["summary"]["anomalies"] == 0
        assert result["summary"]["heuristic_findings"] == 0
        assert result["summary"]["graph_nodes"] == 0
        assert result["summary"]["graph_edges"] == 0

    def test_rename_chain_detection(self):
        engine = CorrelationEngineV2()
        now = datetime.now()
        events = [
            self._make_event(now, EventType.FILE_CREATED, "a.txt", mft=1),
            self._make_event(
                now + timedelta(seconds=5),
                EventType.FILE_RENAMED,
                "b.txt",
                mft=1,
                prev_fname="a.txt",
            ),
            self._make_event(
                now + timedelta(seconds=10),
                EventType.FILE_RENAMED,
                "c.txt",
                mft=1,
                prev_fname="b.txt",
            ),
        ]
        result = engine.analyze(events)
        rename_chains = result["rename_chains"]
        assert len(rename_chains) >= 1
        chain = rename_chains[0]
        assert chain["mft_reference"] == 1
        assert chain["rename_count"] >= 1

    def test_delete_recreate_detection(self):
        engine = CorrelationEngineV2()
        now = datetime.now()
        events = [
            self._make_event(now, EventType.FILE_DELETED, "test.txt", mft=1),
            self._make_event(
                now + timedelta(seconds=10), EventType.FILE_CREATED, "test.txt", mft=1
            ),
        ]
        result = engine.analyze(events)
        delete_recreate = result["delete_recreate"]
        assert len(delete_recreate) >= 1
        entry = delete_recreate[0]
        assert entry["filename"] == "test.txt"
        assert entry["cycle_count"] >= 1

    def test_delete_recreate_multiple_cycles(self):
        engine = CorrelationEngineV2()
        now = datetime.now()
        events = [
            self._make_event(now, EventType.FILE_DELETED, "cycle.txt", mft=1),
            self._make_event(
                now + timedelta(seconds=5), EventType.FILE_CREATED, "cycle.txt", mft=1
            ),
            self._make_event(
                now + timedelta(seconds=10), EventType.FILE_DELETED, "cycle.txt", mft=1
            ),
            self._make_event(
                now + timedelta(seconds=15), EventType.FILE_CREATED, "cycle.txt", mft=1
            ),
        ]
        result = engine.analyze(events)
        delete_recreate = result["delete_recreate"]
        assert len(delete_recreate) >= 1
        assert delete_recreate[0]["cycle_count"] == 2

    def test_anomaly_detection_integration(self):
        engine = CorrelationEngineV2()
        now = datetime.now()
        events = [
            self._make_event(now, EventType.FILE_CREATED, "a.txt", mft=1),
            self._make_event(now - timedelta(hours=1), EventType.FILE_MODIFIED, "a.txt", mft=1),
        ]
        result = engine.analyze(events)
        assert "anomalies" in result
        if result["anomalies"]:
            assert result["anomalies"][0]["type"] == "TIMESTAMP_REVERSAL"

    def test_anomaly_zero_delta_burst(self):
        engine = CorrelationEngineV2()
        ts = datetime.now()
        events = [
            self._make_event(ts, EventType.FILE_CREATED, "burst.txt", mft=1),
            self._make_event(ts, EventType.FILE_MODIFIED, "burst.txt", mft=1),
            self._make_event(ts, EventType.FILE_DELETED, "burst.txt", mft=1),
        ]
        result = engine.analyze(events)
        types = [a["type"] for a in result["anomalies"]]
        assert any(t == "ZERO_DELTA_BURST" for t in types)

    def test_anomaly_rapid_rename(self):
        engine = CorrelationEngineV2()
        now = datetime.now()
        events = [
            self._make_event(now, EventType.FILE_RENAMED, "b.txt", mft=1, prev_fname="a.txt"),
            self._make_event(
                now + timedelta(seconds=2),
                EventType.FILE_RENAMED,
                "c.txt",
                mft=1,
                prev_fname="b.txt",
            ),
        ]
        result = engine.analyze(events)
        types = [a["type"] for a in result["anomalies"]]
        assert any(t == "RAPID_RENAME" for t in types)

    def test_heuristic_integration_mass_delete(self):
        engine = CorrelationEngineV2()
        now = datetime.now()
        events = [
            self._make_event(now + timedelta(seconds=i), EventType.FILE_DELETED, f"f{i}.txt", mft=i)
            for i in range(15)
        ]
        result = engine.analyze(events)
        heuristics = result["heuristics"]
        types = [h["type"] for h in heuristics]
        assert any(t == "MASS_DELETE" for t in types)

    def test_heuristic_integration_suspicious_rename(self):
        engine = CorrelationEngineV2()
        now = datetime.now()
        events = [
            self._make_event(
                now + timedelta(seconds=i),
                EventType.FILE_RENAMED,
                f"name{i}.txt",
                mft=i,
                prev_fname=f"prev{i}.txt",
            )
            for i in range(7)
        ]
        result = engine.analyze(events)
        heuristics = result["heuristics"]
        types = [h["type"] for h in heuristics]
        assert any(t == "SUSPICIOUS_RENAME" for t in types)

    def test_scoring_output(self):
        engine = CorrelationEngineV2()
        now = datetime.now()
        events = [
            self._make_event(now, EventType.FILE_CREATED, "a.txt", mft=1),
            self._make_event(now + timedelta(seconds=5), EventType.FILE_MODIFIED, "a.txt", mft=1),
        ]
        result = engine.analyze(events)
        scores = result["scores"]
        assert len(scores) >= 1
        score = scores[0]
        assert "mft_reference" in score
        assert "filename" in score
        assert "anomaly_score" in score
        assert "heuristic_score" in score
        assert "rename_score" in score
        assert "delete_recreate_score" in score
        assert "total_score" in score
        assert "severity" in score
        assert "tags" in score
        assert score["mft_reference"] == 1
        assert score["filename"] == "a.txt"
        assert isinstance(score["total_score"], float)
        assert isinstance(score["severity"], str)

    def test_scoring_severity_labels(self):
        engine = CorrelationEngineV2()
        now = datetime.now()
        events = [
            self._make_event(now, EventType.FILE_DELETED, "score_test.txt", mft=1),
            self._make_event(
                now + timedelta(seconds=1), EventType.FILE_CREATED, "score_test.txt", mft=1
            ),
            self._make_event(
                now + timedelta(seconds=2), EventType.FILE_DELETED, "score_test.txt", mft=1
            ),
            self._make_event(
                now + timedelta(seconds=3), EventType.FILE_CREATED, "score_test.txt", mft=1
            ),
            self._make_event(
                now + timedelta(seconds=4), EventType.FILE_DELETED, "score_test.txt", mft=1
            ),
            self._make_event(
                now + timedelta(seconds=5), EventType.FILE_CREATED, "score_test.txt", mft=1
            ),
        ]
        result = engine.analyze(events)
        scores = result["scores"]
        assert len(scores) >= 1
        score = scores[0]
        assert score["severity"] in ("critical", "high", "medium", "low", "info")

    def test_clear_method(self):
        engine = CorrelationEngineV2()
        now = datetime.now()
        events = [self._make_event(now, EventType.FILE_CREATED, "test.txt", mft=1)]
        engine.analyze(events)
        assert engine.graph.node_count > 0
        engine.clear()
        assert engine.graph.node_count == 0
        assert engine.graph.edge_count == 0

    def test_graph_is_accessible_via_property(self):
        engine = CorrelationEngineV2()
        graph = engine.graph
        from recoverx.core.correlation.graph import CorrelationGraph

        assert isinstance(graph, CorrelationGraph)

    def test_chain_builder_is_accessible_via_property(self):
        engine = CorrelationEngineV2()
        builder = engine.chain_builder
        from recoverx.core.correlation.chains import ChainBuilder

        assert isinstance(builder, ChainBuilder)

    def test_analyze_with_multiple_events_different_mft(self):
        engine = CorrelationEngineV2()
        now = datetime.now()
        events = [
            self._make_event(now, EventType.FILE_CREATED, "a.txt", mft=1),
            self._make_event(now + timedelta(seconds=1), EventType.FILE_CREATED, "b.txt", mft=2),
            self._make_event(now + timedelta(seconds=2), EventType.FILE_CREATED, "c.txt", mft=3),
        ]
        result = engine.analyze(events)
        scores = result["scores"]
        assert len(scores) == 3
        refs = {s["mft_reference"] for s in scores}
        assert refs == {1, 2, 3}

    def test_analyze_summary_counts(self):
        engine = CorrelationEngineV2()
        now = datetime.now()
        events = [
            self._make_event(now, EventType.FILE_DELETED, "del1.txt", mft=1),
            self._make_event(now + timedelta(seconds=5), EventType.FILE_CREATED, "del1.txt", mft=1),
            self._make_event(
                now + timedelta(seconds=10), EventType.FILE_CREATED, "alone.txt", mft=2
            ),
        ]
        result = engine.analyze(events)
        summary = result["summary"]
        assert isinstance(summary["rename_chains"], int)
        assert isinstance(summary["delete_recreate_chains"], int)
        assert isinstance(summary["graph_nodes"], int)
        assert isinstance(summary["graph_edges"], int)
        assert isinstance(summary["scored_artifacts"], int)

    def test_graph_populated_in_analyze_result(self):
        engine = CorrelationEngineV2()
        now = datetime.now()
        events = [
            self._make_event(now, EventType.FILE_CREATED, "g.txt", mft=1),
            self._make_event(
                now + timedelta(seconds=5),
                EventType.FILE_RENAMED,
                "h.txt",
                mft=1,
                prev_fname="g.txt",
            ),
        ]
        result = engine.analyze(events)
        graph_data = result["graph"]
        assert "nodes" in graph_data
        assert "edges" in graph_data
        assert len(graph_data["nodes"]) >= 2

    def test_multiple_analyze_calls_accumulate_no_state(self):
        engine = CorrelationEngineV2()
        now = datetime.now()
        r1 = engine.analyze(
            [
                self._make_event(now, EventType.FILE_CREATED, "x.txt", mft=1),
            ]
        )
        engine.clear()
        r2 = engine.analyze(
            [
                self._make_event(now, EventType.FILE_DELETED, "y.txt", mft=2),
            ]
        )
        assert len(r1["scores"]) == 1
        assert r1["scores"][0]["mft_reference"] == 1
        assert len(r2["scores"]) == 1
        assert r2["scores"][0]["mft_reference"] == 2
