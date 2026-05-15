from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone

import pytest

from recoverx.core.export.bundle import BundleManifest, ForensicBundle
from recoverx.core.export.package import PackageMetadata, SQLitePackage


class TestBundleManifest:
    def test_defaults(self):
        m = BundleManifest(bundle_id="b-1", created_at="now")
        assert m.bundle_id == "b-1"
        assert m.created_at == "now"
        assert m.version == "1.0"
        assert m.total_events == 0
        assert m.total_findings == 0
        assert m.total_artifacts == 0
        assert m.investigator == ""
        assert m.case_id == ""
        assert m.notes == ""
        assert m.integrity_hash == ""

    def test_to_dict(self):
        m = BundleManifest(
            bundle_id="b-1",
            created_at="2024-01-01T00:00:00",
            version="2.0",
            total_events=10,
            total_findings=5,
            total_artifacts=3,
            investigator="detective",
            case_id="case-42",
            notes="important",
            integrity_hash="abc123",
        )
        d = m.to_dict()
        assert d["bundle_id"] == "b-1"
        assert d["version"] == "2.0"
        assert d["total_events"] == 10
        assert d["total_findings"] == 5
        assert d["total_artifacts"] == 3
        assert d["investigator"] == "detective"
        assert d["case_id"] == "case-42"
        assert d["notes"] == "important"
        assert d["integrity_hash"] == "abc123"


class TestForensicBundle:
    def test_creation(self):
        bundle = ForensicBundle(investigator="alice", case_id="C-001")
        assert bundle.bundle_id is not None
        assert len(bundle.bundle_id) == 16
        assert bundle.manifest.investigator == "alice"
        assert bundle.manifest.case_id == "C-001"

    def test_manifest_property(self):
        bundle = ForensicBundle()
        assert isinstance(bundle.manifest, BundleManifest)
        assert bundle.manifest.bundle_id == bundle.bundle_id

    def test_add_events_updates_manifest(self):
        bundle = ForensicBundle()
        bundle.add_events([{"type": "create"}, {"type": "delete"}])
        assert bundle.manifest.total_events == 2
        bundle.add_events([{"type": "modify"}])
        assert bundle.manifest.total_events == 3

    def test_add_findings_updates_manifest(self):
        bundle = ForensicBundle()
        bundle.add_findings([{"id": "f1"}, {"id": "f2"}])
        assert bundle.manifest.total_findings == 2

    def test_add_artifacts_updates_manifest(self):
        bundle = ForensicBundle()
        bundle.add_artifacts([{"name": "a1"}])
        assert bundle.manifest.total_artifacts == 1

    def test_to_dict_structure(self):
        bundle = ForensicBundle(investigator="bob", case_id="C-002")
        bundle.add_events([{"e": 1}])
        d = bundle.to_dict()
        assert "manifest" in d
        assert "events" in d
        assert "findings" in d
        assert "artifacts" in d
        assert d["manifest"]["investigator"] == "bob"
        assert d["manifest"]["case_id"] == "C-002"
        assert len(d["events"]) == 1
        assert d["findings"] == []
        assert d["artifacts"] == []

    def test_to_json_valid(self):
        bundle = ForensicBundle(investigator="carol", case_id="C-003")
        bundle.add_events([{"e": 1}])
        raw = bundle.to_json()
        parsed = json.loads(raw)
        assert parsed["manifest"]["investigator"] == "carol"
        assert parsed["manifest"]["case_id"] == "C-003"
        assert len(parsed["events"]) == 1

    def test_export_writes_file(self):
        bundle = ForensicBundle(investigator="dave", case_id="C-004")
        bundle.add_events([{"e": 1}])
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            path = tmp.name
        try:
            result = bundle.export(path)
            assert result == path
            assert os.path.isfile(path)
            with open(path) as f:
                parsed = json.load(f)
            assert parsed["manifest"]["investigator"] == "dave"
        finally:
            if os.path.isfile(path):
                os.unlink(path)


class TestPackageMetadata:
    def test_defaults(self):
        m = PackageMetadata(package_id="p-1", created_at="now")
        assert m.package_id == "p-1"
        assert m.created_at == "now"
        assert m.version == "1.0"
        assert m.case_id == ""
        assert m.investigator == ""
        assert m.description == ""

    def test_to_dict(self):
        m = PackageMetadata(
            package_id="p-1",
            created_at="2024-01-01T00:00:00",
            version="2.0",
            case_id="C-005",
            investigator="eve",
            description="test pkg",
        )
        d = m.to_dict()
        assert d["package_id"] == "p-1"
        assert d["version"] == "2.0"
        assert d["case_id"] == "C-005"
        assert d["investigator"] == "eve"
        assert d["description"] == "test pkg"


class TestSQLitePackage:
    @pytest.fixture
    def db_path(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            path = tmp.name
        yield path
        if os.path.isfile(path):
            os.unlink(path)

    def test_create_creates_database(self, db_path):
        pkg = SQLitePackage(db_path, investigator="frank", case_id="C-010")
        pkg.create()
        conn = sqlite3.connect(db_path)
        tables = {
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        assert "package_metadata" in tables
        assert "export_events" in tables
        assert "export_findings" in tables
        assert "export_artifacts" in tables
        conn.close()

    def test_create_stores_metadata(self, db_path):
        pkg = SQLitePackage(db_path, investigator="grace", case_id="C-011")
        pkg.create()
        conn = sqlite3.connect(db_path)
        rows = dict(conn.execute("SELECT key, value FROM package_metadata").fetchall())
        assert rows["package_id"] == pkg._metadata.package_id
        assert rows["created_at"] == pkg._metadata.created_at
        assert rows["version"] == "1.0"
        conn.close()

    def test_write_events(self, db_path):
        pkg = SQLitePackage(db_path, case_id="C-012")
        pkg.create()
        events = [
            {
                "event_type": "create",
                "source": "fs",
                "timestamp": "2024-01-01T00:00:00",
                "filename": "test.txt",
                "mft_reference": 42,
                "confidence": 0.95,
                "notes": "none",
                "case_id": "C-012",
            }
        ]
        count = pkg.write_events(events)
        assert count == 1
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT * FROM export_events").fetchall()
        assert len(rows) == 1
        conn.close()

    def test_write_findings(self, db_path):
        pkg = SQLitePackage(db_path, case_id="C-013")
        pkg.create()
        findings = [
            {
                "id": "f-001",
                "category": "suspicious",
                "severity": "high",
                "confidence": 0.9,
                "title": "Found malware",
                "description": "details",
                "mft_references": [1, 2],
                "case_id": "C-013",
            }
        ]
        count = pkg.write_findings(findings)
        assert count == 1
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT * FROM export_findings").fetchall()
        assert len(rows) == 1
        conn.close()

    def test_write_findings_ignores_duplicates(self, db_path):
        pkg = SQLitePackage(db_path, case_id="C-014")
        pkg.create()
        f = {
            "id": "f-001",
            "category": "test",
            "severity": "low",
            "confidence": 0.5,
            "title": "dup",
            "description": "",
            "mft_references": [],
            "case_id": "C-014",
        }
        pkg.write_findings([f])
        count = pkg.write_findings([f])
        assert count == 0

    def test_metadata_property(self, db_path):
        pkg = SQLitePackage(db_path, investigator="heidi", case_id="C-015")
        assert isinstance(pkg.metadata, PackageMetadata)
        assert pkg.metadata.investigator == "heidi"
        assert pkg.metadata.case_id == "C-015"

    def test_path_property(self, db_path):
        pkg = SQLitePackage(db_path)
        assert pkg.path == db_path
