from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from recoverx.core.forensics.models import ForensicEvent

from .base import Plugin


class FilesystemParserPlugin(Plugin, ABC):
    @abstractmethod
    def parse(self, path: str, offset: int = 0) -> list[ForensicEvent]: ...


class ArtifactProviderPlugin(Plugin, ABC):
    @abstractmethod
    def collect(self, context: dict[str, Any]) -> list[dict[str, Any]]: ...


class ReportExporterPlugin(Plugin, ABC):
    @abstractmethod
    def export(self, data: dict[str, Any], output: str) -> str: ...

    @abstractmethod
    def format_name(self) -> str: ...


class QueryExtensionPlugin(Plugin, ABC):
    @abstractmethod
    def extend_query(self, query: str) -> str: ...

    @abstractmethod
    def custom_operators(self) -> dict[str, str]: ...


class AnalyzerPlugin(Plugin, ABC):
    @abstractmethod
    def analyze(self, events: list[ForensicEvent]) -> list[dict[str, Any]]: ...
