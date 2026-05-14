"""Tests for the centralised signature registry."""

from recoverx.core.carving.signatures import SIGNATURES


class TestSignaturesRegistry:
    def test_all_formats_present(self):
        expected = {"jpg", "png", "gif", "bmp", "pdf"}
        assert set(SIGNATURES.keys()) == expected

    def test_jpg_signature(self):
        s = SIGNATURES["jpg"]
        assert s.name == "JPEG"
        assert s.extension == "jpg"

    def test_png_signature(self):
        s = SIGNATURES["png"]
        assert s.name == "PNG"
        assert s.extension == "png"

    def test_gif_signature(self):
        s = SIGNATURES["gif"]
        assert s.name == "GIF"
        assert s.header == b"GIF8"

    def test_bmp_signature(self):
        s = SIGNATURES["bmp"]
        assert s.name == "BMP"
        assert s.header == b"BM"
        assert s.footer is None

    def test_pdf_signature(self):
        s = SIGNATURES["pdf"]
        assert s.name == "PDF"
        assert s.header == b"%PDF"
        assert s.footer == b"%%EOF"
