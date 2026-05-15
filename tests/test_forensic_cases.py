from __future__ import annotations

import os
import tempfile

from recoverx.core.cases.cases import CaseManager
from recoverx.core.cases.models import Bookmark, CaseMetadata, SavedQuery, TaggedArtifact
from recoverx.core.indexing.storage import StorageBackend


class TestCaseModels:
    def test_case_metadata(self):
        m = CaseMetadata(case_id="abc123", name="Test Case", examiner="examiner1")
        assert m.case_id == "abc123"
        d = m.to_dict()
        assert d["name"] == "Test Case"

    def test_saved_query(self):
        sq = SavedQuery(name="find deletes", query_string='event == "FILE_DELETED"')
        assert sq.name == "find deletes"
        d = sq.to_dict()
        assert d["query_string"] == 'event == "FILE_DELETED"'

    def test_bookmark(self):
        bm = Bookmark(bookmark_id="bm1", case_id="c1", event_id=42, label="suspicious")
        assert bm.event_id == 42
        d = bm.to_dict()
        assert d["label"] == "suspicious"

    def test_tagged_artifact(self):
        ta = TaggedArtifact(tag="malware", artifact_id="art1", case_id="c1")
        assert ta.tag == "malware"


class TestCaseManager:
    def test_create_and_list_cases(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            storage = StorageBackend(db_path, read_only=False)
            storage.open()
            cm = CaseManager(storage)

            case = cm.create_case("Test Investigation", "A test case", "forensic_examiner")
            assert case.case_id is not None
            assert case.metadata.name == "Test Investigation"

            cases = cm.list_cases()
            assert len(cases) >= 1
            assert cases[0].name == "Test Investigation"

            storage.close()
        finally:
            os.unlink(db_path)

    def test_case_bookmarks(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            storage = StorageBackend(db_path, read_only=False)
            storage.open()
            cm = CaseManager(storage)
            case = cm.create_case("Bookmark Test")

            bm = case.add_bookmark(event_id=100, notes="Interesting event", label="suspicious")
            assert bm.event_id == 100

            bookmarks = case.get_bookmarks()
            assert len(bookmarks) == 1
            assert bookmarks[0].label == "suspicious"

            case.remove_bookmark(bm.bookmark_id)
            assert len(case.get_bookmarks()) == 0

            storage.close()
        finally:
            os.unlink(db_path)

    def test_saved_queries(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            storage = StorageBackend(db_path, read_only=False)
            storage.open()
            cm = CaseManager(storage)
            case = cm.create_case("Query Test")

            sq = case.save_query(
                "Find Deletes", 'event == "FILE_DELETED"', "Find all deleted files"
            )
            assert sq.name == "Find Deletes"

            queries = case.get_saved_queries()
            assert len(queries) == 1

            case.delete_query(sq.query_id)
            assert len(case.get_saved_queries()) == 0

            storage.close()
        finally:
            os.unlink(db_path)

    def test_case_tags(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            storage = StorageBackend(db_path, read_only=False)
            storage.open()
            cm = CaseManager(storage)
            case = cm.create_case("Tag Test")

            ta = case.tag_artifact("art1", "malware", "MFT")
            assert ta.tag == "malware"

            tagged = case.get_tagged_artifacts("malware")
            assert len(tagged) == 1

            case.remove_tag("art1", "malware")
            assert len(case.get_tagged_artifacts("malware")) == 0

            storage.close()
        finally:
            os.unlink(db_path)

    def test_close_reopen_case(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            storage = StorageBackend(db_path, read_only=False)
            storage.open()
            cm = CaseManager(storage)
            case = cm.create_case("Close Test")
            case_id = case.case_id

            cm.close_case(case_id)
            cases = cm.list_cases("closed")
            assert any(c.case_id == case_id for c in cases)

            cm.reopen_case(case_id)
            cases = cm.list_cases("open")
            assert any(c.case_id == case_id for c in cases)

            storage.close()
        finally:
            os.unlink(db_path)
