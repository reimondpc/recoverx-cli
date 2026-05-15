from __future__ import annotations

from typing import Any

from recoverx.core.forensics.models import ForensicEvent
from recoverx.plugins.base import Plugin, PluginType
from recoverx.plugins.interfaces import (
    AnalyzerPlugin,
    ArtifactProviderPlugin,
    FilesystemParserPlugin,
    QueryExtensionPlugin,
    ReportExporterPlugin,
)


class FixtureParserPlugin(FilesystemParserPlugin):
    def __init__(self) -> None:
        super().__init__(
            name="fixture_parser",
            version="0.1.0",
            plugin_type=PluginType.FILESYSTEM_PARSER,
        )

    def parse(self, path: str, offset: int = 0) -> list[ForensicEvent]:
        return []


class FixtureAnalyzerPlugin(AnalyzerPlugin):
    def __init__(self) -> None:
        super().__init__(
            name="fixture_analyzer",
            version="1.2.0",
            plugin_type=PluginType.ANALYZER,
        )

    def analyze(self, events: list[ForensicEvent]) -> list[dict[str, Any]]:
        return []


class FixtureExporterPlugin(ReportExporterPlugin):
    def __init__(self) -> None:
        super().__init__(
            name="fixture_exporter",
            version="2.0.0",
            plugin_type=PluginType.REPORT_EXPORTER,
        )

    def export(self, data: dict[str, Any], output: str) -> str:
        return output

    def format_name(self) -> str:
        return "json"
