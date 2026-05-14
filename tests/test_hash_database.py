from __future__ import annotations

import tempfile

from recoverx.core.utils.hash_database import HashDatabase


class TestHashDatabase:
    def test_add_and_known(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            db = HashDatabase(f.name)
        digest = "abc123" * 8
        db.add(digest, "/tmp/test.bin", 1024, "jpg")
        assert db.known(digest)

    def test_is_duplicate(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            db = HashDatabase(f.name)
        data = b"hello world"
        db.add("abc123" * 8, "/tmp/test.bin", len(data), "jpg")
        assert not db.is_duplicate(data)

    def test_statistics(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            db = HashDatabase(f.name)
        db.add("a" * 64, "/tmp/a.bin", 100, "jpg")
        db.add("b" * 64, "/tmp/b.bin", 200, "png")
        stats = db.statistics()
        assert stats["unique_files"] == 2
        assert stats["total_occurrences"] == 2

    def test_clear(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            db = HashDatabase(f.name)
        db.add("x" * 64, "/tmp/x.bin", 50, "pdf")
        db.clear()
        assert db.total_unique == 0

    def test_persistence(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            fname = f.name
        db1 = HashDatabase(fname)
        db1.add("persist" * 8, "/tmp/p.bin", 300, "gif")
        db2 = HashDatabase(fname)
        assert db2.known("persist" * 8)
