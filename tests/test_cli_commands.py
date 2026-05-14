from __future__ import annotations

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
