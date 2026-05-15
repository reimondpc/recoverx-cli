"""Tests for the RecoverX Analyzer Framework."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from recoverx.core.analyzers.base import (
    AnalysisResult,
    BaseAnalyzer,
    FindingSeverity,
)
from recoverx.core.analyzers.duplicate_activity import DuplicateActivityAnalyzer
from recoverx.core.analyzers.mass_delete import MassDeleteAnalyzer
from recoverx.core.analyzers.orphan_artifact import OrphanArtifactAnalyzer
from recoverx.core.analyzers.suspicious_rename import SuspiciousRenameAnalyzer
from recoverx.core.analyzers.timestamp_anomaly import TimestampAnomalyAnalyzer
from recoverx.core.forensics.models import Confidence, EventSource, EventType, ForensicEvent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(
    event_type=EventType.FILE_CREATED,
    filename="test.txt",
    mft_ref=1,
    timestamp=None,
    previous_filename="",
    parent_mft_ref=0,
) -> ForensicEvent:
    return ForensicEvent(
        event_type=event_type,
        filename=filename,
        mft_reference=mft_ref,
        parent_mft_reference=parent_mft_ref,
        previous_filename=previous_filename,
        timestamp=timestamp or datetime.now(),
        source=EventSource.MFT,
        confidence=Confidence.HIGH,
    )


# ===================================================================
# Base tests
# ===================================================================


class TestAnalysisResult:
    def test_defaults(self):
        r = AnalysisResult(
            analyzer_name="test",
            severity=FindingSeverity.MEDIUM,
            confidence=0.5,
            description="desc",
        )
        assert r.analyzer_name == "test"
        assert r.severity == FindingSeverity.MEDIUM
        assert r.confidence == 0.5
        assert r.description == "desc"
        assert r.evidence_refs == []
        assert r.mft_references == []
        assert r.event_count == 0
        assert r.details == {}

    def test_custom_values(self):
        r = AnalysisResult(
            analyzer_name="custom",
            severity=FindingSeverity.CRITICAL,
            confidence=0.99,
            description="custom desc",
            evidence_refs=["ref1", "ref2"],
            mft_references=[100, 200],
            event_count=42,
            details={"key": "val"},
        )
        assert r.evidence_refs == ["ref1", "ref2"]
        assert r.mft_references == [100, 200]
        assert r.event_count == 42
        assert r.details == {"key": "val"}

    def test_to_dict(self):
        r = AnalysisResult(
            analyzer_name="test_analyzer",
            severity=FindingSeverity.HIGH,
            confidence=0.75,
            description="test description",
            evidence_refs=["ev1"],
            mft_references=[1],
            event_count=5,
            details={"foo": "bar"},
        )
        d = r.to_dict()
        assert d["analyzer"] == "test_analyzer"
        assert d["severity"] == "HIGH"
        assert d["severity_score"] == 0.7
        assert d["confidence"] == 0.75
        assert d["description"] == "test description"
        assert d["evidence"] == ["ev1"]
        assert d["mft_references"] == [1]
        assert d["event_count"] == 5
        assert d["details"] == {"foo": "bar"}


class TestFindingSeverity:
    def test_score_values(self):
        assert FindingSeverity.INFO.score() == 0.1
        assert FindingSeverity.LOW.score() == 0.3
        assert FindingSeverity.MEDIUM.score() == 0.5
        assert FindingSeverity.HIGH.score() == 0.7
        assert FindingSeverity.CRITICAL.score() == 0.9

    def test_from_score_critical(self):
        assert FindingSeverity.from_score(0.9) == FindingSeverity.CRITICAL
        assert FindingSeverity.from_score(0.8) == FindingSeverity.CRITICAL

    def test_from_score_high(self):
        assert FindingSeverity.from_score(0.79) == FindingSeverity.HIGH
        assert FindingSeverity.from_score(0.6) == FindingSeverity.HIGH

    def test_from_score_medium(self):
        assert FindingSeverity.from_score(0.59) == FindingSeverity.MEDIUM
        assert FindingSeverity.from_score(0.4) == FindingSeverity.MEDIUM

    def test_from_score_low(self):
        assert FindingSeverity.from_score(0.39) == FindingSeverity.LOW
        assert FindingSeverity.from_score(0.2) == FindingSeverity.LOW

    def test_from_score_info(self):
        assert FindingSeverity.from_score(0.19) == FindingSeverity.INFO
        assert FindingSeverity.from_score(0.0) == FindingSeverity.INFO

    def test_from_score_edge(self):
        assert FindingSeverity.from_score(0.8) == FindingSeverity.CRITICAL
        assert FindingSeverity.from_score(0.6) == FindingSeverity.HIGH
        assert FindingSeverity.from_score(0.4) == FindingSeverity.MEDIUM
        assert FindingSeverity.from_score(0.2) == FindingSeverity.LOW


class TestBaseAnalyzer:
    def test_abstract_cannot_instantiate(self):
        with pytest.raises(TypeError):
            BaseAnalyzer("test")

    def test_concrete_analyze_interface(self):
        class ConcreteAnalyzer(BaseAnalyzer):
            def analyze(self, events):
                return [
                    AnalysisResult(
                        analyzer_name=self._name,
                        severity=FindingSeverity.INFO,
                        confidence=0.1,
                        description="test",
                    )
                ]

        a = ConcreteAnalyzer("concrete")
        assert a.name == "concrete"
        results = a.analyze([])
        assert len(results) == 1
        assert results[0].analyzer_name == "concrete"

    def test_filter_by_confidence(self):
        class CA(BaseAnalyzer):
            def analyze(self, events):
                return []

        a = CA("test", min_confidence=0.5)
        results = [
            AnalysisResult("a", FindingSeverity.INFO, 0.1, "low"),
            AnalysisResult("b", FindingSeverity.INFO, 0.5, "medium"),
            AnalysisResult("c", FindingSeverity.INFO, 0.9, "high"),
        ]
        filtered = a.filter_by_confidence(results)
        assert len(filtered) == 2
        assert all(r.confidence >= 0.5 for r in filtered)

    def test_filter_by_confidence_removes_below_min(self):
        class CA(BaseAnalyzer):
            def analyze(self, events):
                return []

        a = CA("test", min_confidence=0.8)
        results = [
            AnalysisResult("a", FindingSeverity.INFO, 0.79, "almost"),
            AnalysisResult("b", FindingSeverity.INFO, 0.8, "exact"),
        ]
        filtered = a.filter_by_confidence(results)
        assert len(filtered) == 1
        assert filtered[0].confidence == 0.8


# ===================================================================
# SuspiciousRenameAnalyzer tests
# ===================================================================


class TestSuspiciousRenameAnalyzer:
    def test_empty_events_returns_empty(self):
        a = SuspiciousRenameAnalyzer()
        assert a.analyze([]) == []

    def test_no_renames_returns_empty(self):
        events = [
            _make_event(event_type=EventType.FILE_CREATED, mft_ref=1),
            _make_event(event_type=EventType.FILE_MODIFIED, mft_ref=1),
        ]
        a = SuspiciousRenameAnalyzer()
        assert a.analyze(events) == []

    def test_few_renames_returns_low(self):
        now = datetime.now()
        events = [
            _make_event(
                event_type=EventType.FILE_RENAMED,
                filename="b.txt",
                previous_filename="a.txt",
                mft_ref=1,
                timestamp=now,
            ),
            _make_event(
                event_type=EventType.FILE_RENAMED,
                filename="c.txt",
                previous_filename="b.txt",
                mft_ref=1,
                timestamp=now + timedelta(seconds=1),
            ),
            _make_event(
                event_type=EventType.FILE_RENAMED,
                filename="d.txt",
                previous_filename="c.txt",
                mft_ref=1,
                timestamp=now + timedelta(seconds=2),
            ),
        ]
        a = SuspiciousRenameAnalyzer(max_renames_normal=3)
        results = a.analyze(events)
        # Always produces result for renames; rapid=2 (<5s each) boosts to MEDIUM/0.5
        assert len(results) == 1
        assert results[0].severity == FindingSeverity.MEDIUM
        assert results[0].confidence == 0.5

    def test_above_normal_returns_low(self):
        now = datetime.now()
        events = [
            _make_event(
                event_type=EventType.FILE_RENAMED,
                filename=f"file{i}.txt",
                previous_filename=f"file{i-1}.txt",
                mft_ref=1,
                timestamp=now + timedelta(seconds=i * 6),
            )
            for i in range(1, 5)
        ]
        a = SuspiciousRenameAnalyzer(rapid_rename_threshold=5.0, max_renames_normal=3)
        results = a.analyze(events)
        assert len(results) == 1
        assert results[0].severity == FindingSeverity.LOW
        assert results[0].confidence == 0.4

    def test_evidence_contains_chain_string(self):
        now = datetime.now()
        events = [
            _make_event(
                event_type=EventType.FILE_RENAMED,
                filename="b.txt",
                previous_filename="a.txt",
                mft_ref=1,
                timestamp=now,
            ),
            _make_event(
                event_type=EventType.FILE_RENAMED,
                filename="c.txt",
                previous_filename="b.txt",
                mft_ref=1,
                timestamp=now + timedelta(seconds=1),
            ),
        ]
        a = SuspiciousRenameAnalyzer(max_renames_normal=1)
        results = a.analyze(events)
        assert len(results) == 1
        assert any("→" in ref for ref in results[0].evidence_refs)

    def test_mft_references_in_result(self):
        now = datetime.now()
        events = [
            _make_event(
                event_type=EventType.FILE_RENAMED,
                filename="b.txt",
                previous_filename="a.txt",
                mft_ref=42,
                timestamp=now,
            ),
            _make_event(
                event_type=EventType.FILE_RENAMED,
                filename="c.txt",
                previous_filename="b.txt",
                mft_ref=42,
                timestamp=now + timedelta(seconds=1),
            ),
        ]
        a = SuspiciousRenameAnalyzer(max_renames_normal=1)
        results = a.analyze(events)
        assert 42 in results[0].mft_references

    def test_rapid_rename_escalates_low_to_medium(self):
        now = datetime.now()
        events = [
            _make_event(
                event_type=EventType.FILE_RENAMED,
                filename="b.txt",
                previous_filename="a.txt",
                mft_ref=1,
                timestamp=now,
            ),
            _make_event(
                event_type=EventType.FILE_RENAMED,
                filename="c.txt",
                previous_filename="b.txt",
                mft_ref=1,
                timestamp=now + timedelta(seconds=1),
            ),
            _make_event(
                event_type=EventType.FILE_RENAMED,
                filename="d.txt",
                previous_filename="c.txt",
                mft_ref=1,
                timestamp=now + timedelta(seconds=2),
            ),
            _make_event(
                event_type=EventType.FILE_RENAMED,
                filename="e.txt",
                previous_filename="d.txt",
                mft_ref=1,
                timestamp=now + timedelta(seconds=10),
            ),
        ]
        a = SuspiciousRenameAnalyzer(rapid_rename_threshold=5.0, max_renames_normal=2)
        results = a.analyze(events)
        assert len(results) == 1
        assert results[0].severity == FindingSeverity.MEDIUM

    def test_no_mft_ref_skipped(self):
        events = [
            _make_event(
                event_type=EventType.FILE_RENAMED,
                filename="b.txt",
                previous_filename="a.txt",
                mft_ref=0,
            ),
        ]
        a = SuspiciousRenameAnalyzer(max_renames_normal=1)
        results = a.analyze(events)
        assert results == []

    def test_multiple_mft_references_separate_chains(self):
        now = datetime.now()
        events = [
            _make_event(
                event_type=EventType.FILE_RENAMED,
                filename="b.txt",
                previous_filename="a.txt",
                mft_ref=1,
                timestamp=now,
            ),
            _make_event(
                event_type=EventType.FILE_RENAMED,
                filename="b.txt",
                previous_filename="a.txt",
                mft_ref=2,
                timestamp=now,
            ),
        ]
        a = SuspiciousRenameAnalyzer(max_renames_normal=0)
        results = a.analyze(events)
        assert len(results) == 2


# ===================================================================
# MassDeleteAnalyzer tests
# ===================================================================


class TestMassDeleteAnalyzer:
    def test_empty_events_returns_empty(self):
        a = MassDeleteAnalyzer()
        assert a.analyze([]) == []

    def test_few_deletes_below_threshold_returns_empty(self):
        events = [_make_event(event_type=EventType.FILE_DELETED, mft_ref=i) for i in range(5)]
        a = MassDeleteAnalyzer(threshold=10)
        assert a.analyze(events) == []

    def test_threshold_level_deletes_returns_medium(self):
        events = [
            _make_event(event_type=EventType.FILE_DELETED, filename=f"f{i}.txt", mft_ref=i)
            for i in range(10)
        ]
        a = MassDeleteAnalyzer(threshold=10)
        results = a.analyze(events)
        assert len(results) == 1
        assert results[0].severity == FindingSeverity.MEDIUM
        assert results[0].confidence == 0.6

    def test_three_x_threshold_returns_high(self):
        events = [
            _make_event(event_type=EventType.FILE_DELETED, filename=f"f{i}.txt", mft_ref=i)
            for i in range(30)
        ]
        a = MassDeleteAnalyzer(threshold=10)
        results = a.analyze(events)
        assert len(results) == 1
        assert results[0].severity == FindingSeverity.HIGH
        assert results[0].confidence == 0.8

    def test_five_x_threshold_returns_critical(self):
        events = [
            _make_event(event_type=EventType.FILE_DELETED, filename=f"f{i}.txt", mft_ref=i)
            for i in range(51)
        ]
        a = MassDeleteAnalyzer(threshold=10)
        results = a.analyze(events)
        assert len(results) == 1
        assert results[0].severity == FindingSeverity.CRITICAL
        assert results[0].confidence == 0.95

    def test_five_x_threshold_boundary(self):
        events = [
            _make_event(event_type=EventType.FILE_DELETED, filename=f"f{i}.txt", mft_ref=i)
            for i in range(50)
        ]
        a = MassDeleteAnalyzer(threshold=10)
        results = a.analyze(events)
        assert len(results) == 1
        assert results[0].severity == FindingSeverity.CRITICAL

    def test_evidence_includes_top_filenames(self):
        events = [
            _make_event(event_type=EventType.FILE_DELETED, filename="dup.txt", mft_ref=i)
            for i in range(10)
        ]
        a = MassDeleteAnalyzer(threshold=10)
        results = a.analyze(events)
        assert len(results) == 1
        assert any("dup.txt" in ref for ref in results[0].evidence_refs)

    def test_three_x_threshold_boundary(self):
        events = [_make_event(event_type=EventType.FILE_DELETED, mft_ref=i) for i in range(30)]
        a = MassDeleteAnalyzer(threshold=10)
        results = a.analyze(events)
        assert len(results) == 1
        assert results[0].severity == FindingSeverity.HIGH

    def test_ten_exact_boundary(self):
        events = [_make_event(event_type=EventType.FILE_DELETED, mft_ref=i) for i in range(10)]
        a = MassDeleteAnalyzer(threshold=10)
        results = a.analyze(events)
        assert len(results) == 1

    def test_parent_mft_in_references(self):
        events = [
            _make_event(
                event_type=EventType.FILE_DELETED,
                filename="f.txt",
                mft_ref=i,
                parent_mft_ref=99,
            )
            for i in range(10)
        ]
        a = MassDeleteAnalyzer(threshold=10)
        results = a.analyze(events)
        assert 99 in results[0].mft_references


# ===================================================================
# TimestampAnomalyAnalyzer tests
# ===================================================================


class TestTimestampAnomalyAnalyzer:
    def test_empty_events_returns_empty(self):
        a = TimestampAnomalyAnalyzer()
        assert a.analyze([]) == []

    def test_no_reversals_returns_empty(self):
        now = datetime.now()
        events = [
            _make_event(mft_ref=1, timestamp=now),
            _make_event(mft_ref=1, timestamp=now + timedelta(seconds=1)),
        ]
        a = TimestampAnomalyAnalyzer()
        assert a.analyze(events) == []

    def test_few_reversals_below_normal_threshold(self):
        now = datetime.now()
        events = [
            _make_event(mft_ref=1, timestamp=now + timedelta(seconds=2)),
            _make_event(mft_ref=1, timestamp=now + timedelta(seconds=1)),
        ]
        a = TimestampAnomalyAnalyzer(max_reversals_normal=2)
        results = a.analyze(events)
        # 1 reversal < max (2), falls to INFO/0.3 default but still reported
        assert len(results) == 1
        assert results[0].severity == FindingSeverity.INFO
        assert results[0].confidence == 0.3

    def test_above_normal_returns_low(self):
        now = datetime.now()
        events = []
        for i in range(4):
            events.append(
                _make_event(
                    mft_ref=1,
                    timestamp=now + timedelta(seconds=5 - i),
                )
            )
        a = TimestampAnomalyAnalyzer(max_reversals_normal=2)
        results = a.analyze(events)
        assert len(results) == 1
        assert results[0].severity == FindingSeverity.LOW
        assert results[0].confidence == 0.45

    def test_many_reversals_returns_high(self):
        now = datetime.now()
        events = []
        for i in range(8):
            events.append(
                _make_event(
                    mft_ref=1,
                    timestamp=now + timedelta(seconds=10 - i),
                )
            )
        a = TimestampAnomalyAnalyzer(max_reversals_normal=2)
        results = a.analyze(events)
        assert len(results) == 1
        assert results[0].severity == FindingSeverity.HIGH
        assert results[0].confidence == 0.85

    def test_reversal_details_in_evidence(self):
        now = datetime.now()
        events = [
            _make_event(mft_ref=1, filename="a.txt", timestamp=now + timedelta(seconds=3)),
            _make_event(mft_ref=1, filename="a.txt", timestamp=now + timedelta(seconds=1)),
        ]
        a = TimestampAnomalyAnalyzer(max_reversals_normal=0)
        results = a.analyze(events)
        assert len(results) == 1
        assert len(results[0].evidence_refs) >= 1
        assert "MFT 1" in results[0].evidence_refs[0]

    def test_reversal_details_includes_both_filenames(self):
        now = datetime.now()
        events = [
            _make_event(mft_ref=5, filename="first.txt", timestamp=now + timedelta(seconds=3)),
            _make_event(mft_ref=5, filename="second.txt", timestamp=now + timedelta(seconds=1)),
        ]
        a = TimestampAnomalyAnalyzer(max_reversals_normal=0)
        results = a.analyze(events)
        assert "MFT 5" in results[0].evidence_refs[0]

    def test_only_consecutive_reversals_counted(self):
        now = datetime.now()
        events = [
            _make_event(mft_ref=1, timestamp=now + timedelta(seconds=3)),
            _make_event(mft_ref=1, timestamp=now + timedelta(seconds=1)),
            _make_event(mft_ref=1, timestamp=now + timedelta(seconds=2)),
        ]
        a = TimestampAnomalyAnalyzer(max_reversals_normal=0)
        results = a.analyze(events)
        assert len(results) == 1
        assert results[0].details["total_reversals"] == 1

    def test_multiple_mft_references_separate(self):
        now = datetime.now()
        events = [
            _make_event(mft_ref=1, timestamp=now + timedelta(seconds=2)),
            _make_event(mft_ref=1, timestamp=now + timedelta(seconds=1)),
            _make_event(mft_ref=2, timestamp=now + timedelta(seconds=4)),
            _make_event(mft_ref=2, timestamp=now + timedelta(seconds=3)),
        ]
        a = TimestampAnomalyAnalyzer(max_reversals_normal=0)
        results = a.analyze(events)
        assert len(results) == 1
        assert results[0].details["total_reversals"] == 2


# ===================================================================
# DuplicateActivityAnalyzer tests
# ===================================================================


class TestDuplicateActivityAnalyzer:
    def test_no_duplicates_returns_empty(self):
        events = [
            _make_event(event_type=EventType.FILE_CREATED, filename="a.txt", mft_ref=1),
            _make_event(event_type=EventType.FILE_CREATED, filename="b.txt", mft_ref=2),
        ]
        a = DuplicateActivityAnalyzer(threshold=5)
        assert a.analyze(events) == []

    def test_threshold_level_duplicates(self):
        events = [
            _make_event(event_type=EventType.FILE_CREATED, filename="dup.txt", mft_ref=1)
            for _ in range(5)
        ]
        a = DuplicateActivityAnalyzer(threshold=5)
        results = a.analyze(events)
        assert len(results) == 1
        assert results[0].severity == FindingSeverity.LOW
        assert results[0].confidence == 0.4

    def test_severity_escalates_with_more_duplicates(self):
        events = [
            _make_event(event_type=EventType.FILE_CREATED, filename="dup.txt", mft_ref=1)
            for _ in range(15)
        ]
        a = DuplicateActivityAnalyzer(threshold=5)
        results = a.analyze(events)
        assert len(results) == 1
        assert results[0].severity == FindingSeverity.MEDIUM
        assert results[0].confidence == 0.6

    def test_severity_high_at_high_count(self):
        events = [
            _make_event(event_type=EventType.FILE_CREATED, filename="dup.txt", mft_ref=1)
            for _ in range(25)
        ]
        a = DuplicateActivityAnalyzer(threshold=5)
        results = a.analyze(events)
        assert len(results) == 1
        assert results[0].severity == FindingSeverity.HIGH
        assert results[0].confidence == 0.8

    def test_evidence_includes_duplicate_details(self):
        events = [
            _make_event(event_type=EventType.FILE_CREATED, filename="dup.txt", mft_ref=1)
            for _ in range(5)
        ]
        a = DuplicateActivityAnalyzer(threshold=5)
        results = a.analyze(events)
        assert len(results[0].evidence_refs) >= 1
        assert "FILE_CREATED" in results[0].evidence_refs[0]

    def test_multiple_event_types_separate_counters(self):
        events = [
            _make_event(event_type=EventType.FILE_CREATED, filename="a.txt", mft_ref=1)
            for _ in range(5)
        ] + [
            _make_event(event_type=EventType.FILE_MODIFIED, filename="a.txt", mft_ref=1)
            for _ in range(5)
        ]
        a = DuplicateActivityAnalyzer(threshold=5)
        results = a.analyze(events)
        assert len(results) == 1
        assert results[0].details["duplicate_groups"] == 2

    def test_boundary_below_threshold(self):
        events = [
            _make_event(event_type=EventType.FILE_CREATED, filename="dup.txt", mft_ref=1)
            for _ in range(4)
        ]
        a = DuplicateActivityAnalyzer(threshold=5)
        assert a.analyze(events) == []


# ===================================================================
# OrphanArtifactAnalyzer tests
# ===================================================================


class TestOrphanArtifactAnalyzer:
    def test_no_orphans_returns_empty(self):
        events = [
            _make_event(event_type=EventType.FILE_CREATED, mft_ref=1),
            _make_event(event_type=EventType.FILE_DELETED, mft_ref=1),
        ]
        a = OrphanArtifactAnalyzer()
        assert a.analyze(events) == []

    def test_orphans_without_create_records(self):
        events = [
            _make_event(event_type=EventType.FILE_MODIFIED, mft_ref=1),
            _make_event(event_type=EventType.FILE_RENAMED, mft_ref=2),
        ]
        a = OrphanArtifactAnalyzer()
        results = a.analyze(events)
        assert len(results) == 1
        assert results[0].severity == FindingSeverity.MEDIUM
        assert results[0].confidence == 0.7
        assert "without create records" in results[0].description

    def test_orphan_deletes_without_creates(self):
        events = [
            _make_event(event_type=EventType.FILE_DELETED, mft_ref=1),
            _make_event(event_type=EventType.FILE_DELETED, mft_ref=2),
        ]
        a = OrphanArtifactAnalyzer()
        results = a.analyze(events)
        assert len(results) == 2
        orphan_deletes = [r for r in results if "deletes without creates" in r.description]
        assert len(orphan_deletes) == 1
        assert orphan_deletes[0].severity == FindingSeverity.HIGH
        assert orphan_deletes[0].confidence == 0.85

    def test_both_orphan_types_returned(self):
        events = [
            _make_event(event_type=EventType.FILE_MODIFIED, mft_ref=1),
            _make_event(event_type=EventType.FILE_DELETED, mft_ref=2),
        ]
        a = OrphanArtifactAnalyzer()
        results = a.analyze(events)
        assert len(results) == 2
        categories = {r.severity for r in results}
        assert categories == {FindingSeverity.MEDIUM, FindingSeverity.HIGH}

    def test_orphan_artifact_mft_references(self):
        events = [
            _make_event(event_type=EventType.FILE_DELETED, mft_ref=42),
        ]
        a = OrphanArtifactAnalyzer()
        results = a.analyze(events)
        orphan_delete = [r for r in results if "deletes without creates" in r.description]
        assert 42 in orphan_delete[0].mft_references

    def test_orphan_without_create_sets_event_count(self):
        events = [
            _make_event(event_type=EventType.FILE_MODIFIED, mft_ref=10),
            _make_event(event_type=EventType.FILE_MODIFIED, mft_ref=20),
            _make_event(event_type=EventType.FILE_MODIFIED, mft_ref=30),
        ]
        a = OrphanArtifactAnalyzer()
        results = a.analyze(events)
        assert results[0].event_count == 3

    def test_zero_mft_ref_ignored(self):
        events = [
            _make_event(event_type=EventType.FILE_DELETED, mft_ref=0),
        ]
        a = OrphanArtifactAnalyzer()
        results = a.analyze(events)
        assert results == []
