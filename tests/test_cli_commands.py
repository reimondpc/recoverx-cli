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
        assert "--quick" in out
        assert "--max-size" in out
        assert "--max-time" in out
        assert "--output" in out
        assert "--type" in out
        assert "--live-findings" in out

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


class TestScanHelpers:
    def test_parse_size(self):
        from recoverx.cli.commands.scan import _parse_size

        assert _parse_size("2GB") == 2 * 1024**3
        assert _parse_size("500MB") == 500 * 1024**2
        assert _parse_size("1KB") == 1024
        assert _parse_size("1048576") == 1048576

    def test_parse_time(self):
        from recoverx.cli.commands.scan import _parse_time

        assert _parse_time("5m") == 300.0
        assert _parse_time("30s") == 30.0
        assert _parse_time("1h") == 3600.0
        assert _parse_time("90") == 90.0

    def test_resolve_carvers(self):
        from recoverx.cli.commands.scan import _resolve_carvers

        carvers = _resolve_carvers("jpg,png")
        assert len(carvers) == 2

        carvers = _resolve_carvers(None)
        assert len(carvers) == 5

    def test_resolve_carvers_invalid(self):
        import typer

        from recoverx.cli.commands.scan import _resolve_carvers

        try:
            _resolve_carvers("invalid_format")
            assert False, "should have raised"
        except typer.BadParameter:
            pass

    def test_scan_progress(self):
        from recoverx.core.scanning import ScanProgress

        p = ScanProgress(1000)
        assert p.total_bytes == 1000
        assert p.scanned == 0
        p.update(500)
        assert p.scanned == 500
        assert p.percentage == 50.0
        p.add_finding("JPEG")
        p.add_finding("JPEG")
        p.add_finding("PNG")
        assert p.findings_counts == {"JPEG": 2, "PNG": 1}

    def test_scan_interrupt_handler(self):
        from recoverx.core.scanning import InterruptHandler

        h = InterruptHandler()
        assert not h.interrupted
        h.install()
        h.restore()
        assert not h.interrupted
