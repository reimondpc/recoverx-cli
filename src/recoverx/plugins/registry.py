from __future__ import annotations

from typing import Any

from .base import Plugin, PluginType
from .interfaces import (
    AnalyzerPlugin,
    ArtifactProviderPlugin,
    FilesystemParserPlugin,
    QueryExtensionPlugin,
    ReportExporterPlugin,
)


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}
        self._by_type: dict[PluginType, list[Plugin]] = {}

    def register(self, plugin: Plugin) -> None:
        self._plugins[plugin.name] = plugin
        self._by_type.setdefault(plugin.plugin_type, []).append(plugin)

    def unregister(self, name: str) -> None:
        plugin = self._plugins.pop(name, None)
        if plugin:
            lst = self._by_type.get(plugin.plugin_type, [])
            if plugin in lst:
                lst.remove(plugin)

    def get(self, name: str) -> Plugin | None:
        return self._plugins.get(name)

    def get_by_type(self, plugin_type: PluginType) -> list[Plugin]:
        return list(self._by_type.get(plugin_type, []))

    def get_parsers(self) -> list[FilesystemParserPlugin]:
        return [
            p
            for p in self.get_by_type(PluginType.FILESYSTEM_PARSER)
            if isinstance(p, FilesystemParserPlugin)
        ]

    def get_artifact_providers(self) -> list[ArtifactProviderPlugin]:
        return [
            p
            for p in self.get_by_type(PluginType.ARTIFACT_PROVIDER)
            if isinstance(p, ArtifactProviderPlugin)
        ]

    def get_exporters(self) -> list[ReportExporterPlugin]:
        return [
            p
            for p in self.get_by_type(PluginType.REPORT_EXPORTER)
            if isinstance(p, ReportExporterPlugin)
        ]

    def get_query_extensions(self) -> list[QueryExtensionPlugin]:
        return [
            p
            for p in self.get_by_type(PluginType.QUERY_EXTENSION)
            if isinstance(p, QueryExtensionPlugin)
        ]

    def get_analyzers(self) -> list[AnalyzerPlugin]:
        return [p for p in self.get_by_type(PluginType.ANALYZER) if isinstance(p, AnalyzerPlugin)]

    def list_all(self) -> list[dict[str, Any]]:
        return [p.metadata() for p in self._plugins.values()]

    @property
    def count(self) -> int:
        return len(self._plugins)
