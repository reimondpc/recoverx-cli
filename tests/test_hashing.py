"""Tests for SHA-256 hashing utilities."""

from __future__ import annotations

from recoverx.core.utils.hashing import HashManager, sha256, sha256_file


class TestSHA256:
    def test_sha256_known_value(self):
        digest = sha256(b"hello")
        assert digest == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"

    def test_sha256_empty(self):
        digest = sha256(b"")
        assert digest == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def test_sha256_file(self, tmp_path):
        f = tmp_path / "test.bin"
        f.write_bytes(b"hello world")
        digest = sha256_file(str(f))
        expected = sha256(b"hello world")
        assert digest == expected


class TestHashManager:
    def test_compute_and_duplicate(self):
        mgr = HashManager()
        d1 = mgr.compute(b"data1")
        d2 = mgr.compute(b"data1")
        assert d1 == d2
        assert mgr.unique_count == 1

    def test_unique_count(self):
        mgr = HashManager()
        mgr.compute(b"a")
        mgr.compute(b"b")
        mgr.compute(b"a")
        assert mgr.unique_count == 2

    def test_is_duplicate(self):
        mgr = HashManager()
        d = mgr.compute(b"test")
        assert mgr.is_duplicate(d)
        assert not mgr.is_duplicate(
            "0000000000000000000000000000000000000000000000000000000000000000"
        )

    def test_check_integrity(self, tmp_path):
        f = tmp_path / "test.bin"
        f.write_bytes(b"integrity check")
        mgr = HashManager()
        d = mgr.compute(b"integrity check")
        assert mgr.check_integrity(str(f), d)
        assert not mgr.check_integrity(str(f), "0" * 64)
