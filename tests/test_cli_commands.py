from __future__ import annotations

import os

# Must be set before importing app to prevent Rich/Typer ANSI output
os.environ["NO_COLOR"] = "1"
os.environ.pop("FORCE_COLOR", None)

from typer.testing import CliRunner

from recoverx.cli.commands.devices import detect_raw_devices
from recoverx.cli.main import app

runner = CliRunner()


class TestCLICommands:
    def test_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "recoverx" in result.stdout

    def test_info_help(self):
        result = runner.invoke(app, ["info", "--help"])
        assert result.exit_code == 0

    def test_scan_help(self):
        result = runner.invoke(app, ["scan", "--help"])
        assert result.exit_code == 0
        assert "--threads" in result.stdout
        assert "--report" in result.stdout
        assert "--no-mmap" in result.stdout
        assert "--chunk-size" in result.stdout

    def test_devices_help(self):
        result = runner.invoke(app, ["devices", "--help"])
        assert result.exit_code == 0
        assert "--detailed" in result.stdout

    def test_detect_raw_devices(self):
        devices = detect_raw_devices()
        assert isinstance(devices, list)

    # ── forensic commands ──────────────────────────────────────────────

    def test_forensic_help(self):
        result = runner.invoke(app, ["forensic", "--help"])
        assert result.exit_code == 0
        assert "timeline" in result.stdout

    def test_forensic_timeline_help(self):
        result = runner.invoke(app, ["forensic", "timeline", "--help"])
        assert result.exit_code == 0
        assert "--since" in result.stdout
        assert "--until" in result.stdout
        assert "--format" in result.stdout
        assert "--output" in result.stdout
        assert "--limit" in result.stdout
        assert "--json" in result.stdout

    def test_forensic_timeline_missing_path(self):
        result = runner.invoke(app, ["forensic", "timeline"])
        assert result.exit_code != 0

    def test_forensic_timeline_bad_path(self):
        result = runner.invoke(app, ["forensic", "timeline", "/nonexistent/image.raw"])
        assert result.exit_code != 0

    # ── NTFS USN command ──────────────────────────────────────────────

    def test_ntfs_usn_help(self):
        result = runner.invoke(app, ["ntfs", "usn", "--help"])
        assert result.exit_code == 0
        assert "--json" in result.stdout

    def test_ntfs_usn_missing_path(self):
        result = runner.invoke(app, ["ntfs", "usn"])
        assert result.exit_code != 0

    # ── NTFS LogFile command ──────────────────────────────────────────

    def test_ntfs_logfile_help(self):
        result = runner.invoke(app, ["ntfs", "logfile", "--help"])
        assert result.exit_code == 0
        assert "--json" in result.stdout

    def test_ntfs_logfile_missing_path(self):
        result = runner.invoke(app, ["ntfs", "logfile"])
        assert result.exit_code != 0

    # ── new v0.7.5 forensic commands ─────────────────────────────────

    def test_forensic_search_help(self):
        result = runner.invoke(app, ["forensic", "search", "--help"])
        assert result.exit_code == 0
        assert "--name" in result.stdout
        assert "--event" in result.stdout
        assert "--hash" in result.stdout
        assert "--deleted-only" in result.stdout
        assert "--since" in result.stdout
        assert "--limit" in result.stdout

    def test_forensic_search_missing_path(self):
        result = runner.invoke(app, ["forensic", "search"])
        assert result.exit_code != 0

    def test_forensic_query_help(self):
        result = runner.invoke(app, ["forensic", "query", "--help"])
        assert result.exit_code == 0
        assert "--explain" in result.stdout
        assert "--limit" in result.stdout

    def test_forensic_query_missing_args(self):
        result = runner.invoke(app, ["forensic", "query"])
        assert result.exit_code != 0

    def test_forensic_export_help(self):
        result = runner.invoke(app, ["forensic", "export", "--help"])
        assert result.exit_code == 0
        assert "--format" in result.stdout
        assert "--output" in result.stdout

    def test_forensic_export_missing_path(self):
        result = runner.invoke(app, ["forensic", "export"])
        assert result.exit_code != 0

    def test_forensic_summary_help(self):
        result = runner.invoke(app, ["forensic", "summary", "--help"])
        assert result.exit_code == 0
        assert "--json" in result.stdout

    def test_forensic_summary_bad_path(self):
        result = runner.invoke(app, ["forensic", "summary", "/nonexistent.img"])
        assert result.exit_code != 0

    def test_forensic_index_help(self):
        result = runner.invoke(app, ["forensic", "index", "--help"])
        assert result.exit_code == 0
        assert "--force" in result.stdout

    def test_forensic_index_missing_path(self):
        result = runner.invoke(app, ["forensic", "index"])
        assert result.exit_code != 0

    def test_forensic_index_stats_help(self):
        result = runner.invoke(app, ["forensic", "index-stats", "--help"])
        assert result.exit_code == 0

    def test_forensic_index_stats_missing_path(self):
        result = runner.invoke(app, ["forensic", "index-stats"])
        assert result.exit_code != 0
