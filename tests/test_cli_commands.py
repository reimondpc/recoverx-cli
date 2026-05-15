from __future__ import annotations

import re

from typer.testing import CliRunner

from recoverx.cli.commands.devices import detect_raw_devices
from recoverx.cli.main import app

runner = CliRunner()

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


class TestCLICommands:
    def test_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "recoverx" in _strip_ansi(result.stdout)

    def test_info_help(self):
        result = runner.invoke(app, ["info", "--help"])
        assert result.exit_code == 0

    def test_scan_help(self):
        result = runner.invoke(app, ["scan", "--help"])
        assert result.exit_code == 0
        out = _strip_ansi(result.stdout)
        assert "--threads" in out
        assert "--report" in out
        assert "--no-mmap" in out
        assert "--chunk-size" in out

    def test_devices_help(self):
        result = runner.invoke(app, ["devices", "--help"])
        assert result.exit_code == 0
        assert "--detailed" in _strip_ansi(result.stdout)

    def test_detect_raw_devices(self):
        devices = detect_raw_devices()
        assert isinstance(devices, list)

    # ── forensic commands ──────────────────────────────────────────────

    def test_forensic_help(self):
        result = runner.invoke(app, ["forensic", "--help"])
        assert result.exit_code == 0
        assert "timeline" in _strip_ansi(result.stdout)

    def test_forensic_timeline_help(self):
        result = runner.invoke(app, ["forensic", "timeline", "--help"])
        assert result.exit_code == 0
        out = _strip_ansi(result.stdout)
        assert "--since" in out
        assert "--until" in out
        assert "--format" in out
        assert "--output" in out
        assert "--limit" in out
        assert "--json" in out

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
        assert "--json" in _strip_ansi(result.stdout)

    def test_ntfs_usn_missing_path(self):
        result = runner.invoke(app, ["ntfs", "usn"])
        assert result.exit_code != 0

    # ── NTFS LogFile command ──────────────────────────────────────────

    def test_ntfs_logfile_help(self):
        result = runner.invoke(app, ["ntfs", "logfile", "--help"])
        assert result.exit_code == 0
        assert "--json" in _strip_ansi(result.stdout)

    def test_ntfs_logfile_missing_path(self):
        result = runner.invoke(app, ["ntfs", "logfile"])
        assert result.exit_code != 0

    # ── new v0.7.5 forensic commands ─────────────────────────────────

    def test_forensic_search_help(self):
        result = runner.invoke(app, ["forensic", "search", "--help"])
        assert result.exit_code == 0
        out = _strip_ansi(result.stdout)
        assert "--name" in out
        assert "--event" in out
        assert "--hash" in out
        assert "--deleted-only" in out
        assert "--since" in out
        assert "--limit" in out

    def test_forensic_search_missing_path(self):
        result = runner.invoke(app, ["forensic", "search"])
        assert result.exit_code != 0

    def test_forensic_query_help(self):
        result = runner.invoke(app, ["forensic", "query", "--help"])
        assert result.exit_code == 0
        out = _strip_ansi(result.stdout)
        assert "--explain" in out
        assert "--limit" in out

    def test_forensic_query_missing_args(self):
        result = runner.invoke(app, ["forensic", "query"])
        assert result.exit_code != 0

    def test_forensic_export_help(self):
        result = runner.invoke(app, ["forensic", "export", "--help"])
        assert result.exit_code == 0
        out = _strip_ansi(result.stdout)
        assert "--format" in out
        assert "--output" in out

    def test_forensic_export_missing_path(self):
        result = runner.invoke(app, ["forensic", "export"])
        assert result.exit_code != 0

    def test_forensic_summary_help(self):
        result = runner.invoke(app, ["forensic", "summary", "--help"])
        assert result.exit_code == 0
        assert "--json" in _strip_ansi(result.stdout)

    def test_forensic_summary_bad_path(self):
        result = runner.invoke(app, ["forensic", "summary", "/nonexistent.img"])
        assert result.exit_code != 0

    def test_forensic_index_help(self):
        result = runner.invoke(app, ["forensic", "index", "--help"])
        assert result.exit_code == 0
        assert "--force" in _strip_ansi(result.stdout)

    def test_forensic_index_missing_path(self):
        result = runner.invoke(app, ["forensic", "index"])
        assert result.exit_code != 0

    def test_forensic_index_stats_help(self):
        result = runner.invoke(app, ["forensic", "index-stats", "--help"])
        assert result.exit_code == 0

    def test_forensic_index_stats_missing_path(self):
        result = runner.invoke(app, ["forensic", "index-stats"])
        assert result.exit_code != 0
