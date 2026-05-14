from __future__ import annotations

import os
import tempfile

from typer.testing import CliRunner

from recoverx.cli.main import app
from tests.fat32.create_fat32_image import create_test_image

runner = CliRunner()


class TestFAT32CLI:
    def test_fat32_info(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = create_test_image(tmp)
            result = runner.invoke(app, ["fat32", "info", path])
            assert result.exit_code == 0
            assert "FAT32 Boot Sector" in result.stdout
            assert "RECOVERX" in result.stdout

    def test_fat32_info_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = create_test_image(tmp)
            result = runner.invoke(app, ["fat32", "info", path, "--json"])
            assert result.exit_code == 0
            assert "volume_label" in result.stdout

    def test_fat32_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = create_test_image(tmp)
            result = runner.invoke(app, ["fat32", "list", path])
            assert result.exit_code == 0
            assert "README" in result.stdout

    def test_fat32_list_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = create_test_image(tmp)
            result = runner.invoke(app, ["fat32", "list", path, "--json"])
            assert result.exit_code == 0
            assert "filesystem" in result.stdout

    def test_fat32_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = create_test_image(tmp)
            result = runner.invoke(app, ["fat32", "deleted", path])
            assert result.exit_code == 0
            assert "Deleted Files" in result.stdout

    def test_fat32_recover(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = create_test_image(tmp)
            out_dir = os.path.join(tmp, "recovered")
            result = runner.invoke(app, ["fat32", "recover", path, "--output", out_dir])
            assert result.exit_code == 0
            assert "Recovery complete" in result.stdout

    def test_fat32_recover_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = create_test_image(tmp)
            result = runner.invoke(app, ["fat32", "recover", path, "--json"])
            assert result.exit_code == 0
            assert "recovered_files" in result.stdout

    def test_fat32_info_nonexistent(self):
        result = runner.invoke(app, ["fat32", "info", "/nonexistent.img"])
        assert result.exit_code != 0

    def test_fat32_help(self):
        result = runner.invoke(app, ["fat32", "--help"])
        assert result.exit_code == 0
        assert "info" in result.stdout
        assert "list" in result.stdout
        assert "deleted" in result.stdout
        assert "recover" in result.stdout
