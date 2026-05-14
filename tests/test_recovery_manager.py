"""Tests for the RecoveryManager."""

from __future__ import annotations

from recoverx.core.carving.base import CarvedFile
from recoverx.core.recovery.manager import RecoveryManager


class TestRecoveryManager:
    def test_save_creates_file(self, tmp_path):
        mgr = RecoveryManager(output_dir=str(tmp_path))
        carved = CarvedFile(
            data=b"test-data",
            offset_start=100,
            offset_end=110,
            signature_name="JPEG",
            extension="jpg",
        )
        path = mgr.save(carved)
        assert path.exists()
        assert path.read_bytes() == b"test-data"
        assert path.name == "jpeg_001.jpg"

    def test_save_increments_counter(self, tmp_path):
        mgr = RecoveryManager(output_dir=str(tmp_path))
        for i in range(3):
            carved = CarvedFile(
                data=b"x" * 10,
                offset_start=i * 100,
                offset_end=i * 100 + 10,
                signature_name="JPEG",
                extension="jpg",
            )
            mgr.save(carved)
        assert (tmp_path / "jpeg_003.jpg").exists()
        assert mgr.total_files == 3

    def test_save_different_extensions(self, tmp_path):
        mgr = RecoveryManager(output_dir=str(tmp_path))
        for ext, name in [("jpg", "JPEG"), ("png", "PNG")]:
            carved = CarvedFile(
                data=b"data",
                offset_start=0,
                offset_end=4,
                signature_name=name,
                extension=ext,
            )
            mgr.save(carved)
        assert (tmp_path / "jpeg_001.jpg").exists()
        assert (tmp_path / "png_001.png").exists()
        assert mgr.total_files == 2

    def test_total_files_property(self, tmp_path):
        mgr = RecoveryManager(output_dir=str(tmp_path))
        assert mgr.total_files == 0
        mgr.save(CarvedFile(b"a", 0, 1, "JPEG", "jpg"))
        assert mgr.total_files == 1
