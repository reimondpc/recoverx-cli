"""Tests for the file signatures registry."""

from __future__ import annotations

from recoverx.core.carving.signatures import SIGNATURES


class TestSignatures:
    def test_jpg_signature_exists(self):
        assert "jpg" in SIGNATURES

    def test_jpg_signature_values(self):
        sig = SIGNATURES["jpg"]
        assert sig.name == "JPEG"
        assert sig.extension == "jpg"
        assert sig.header == b"\xff\xd8\xff"
        assert sig.footer == b"\xff\xd9"
        assert sig.min_size == 128

    def test_signatures_are_immutable_type(self):
        for key, sig in SIGNATURES.items():
            assert isinstance(key, str)
            assert isinstance(sig.name, str)
            assert isinstance(sig.extension, str)
            assert isinstance(sig.header, bytes)
