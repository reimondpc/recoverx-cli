from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class PluginType(Enum):
    FILESYSTEM_PARSER = auto()
    ARTIFACT_PROVIDER = auto()
    REPORT_EXPORTER = auto()
    QUERY_EXTENSION = auto()
    ANALYZER = auto()
    ACQUISITION_PROVIDER = auto()
    DISTRIBUTED_WORKER = auto()
    TRANSPORT = auto()


@dataclass
class PluginCapabilities:
    parallel_safe: bool = False
    streaming: bool = False
    incremental: bool = False
    resumable: bool = False
    bounded_memory: bool = True
    supports_batch: bool = False


class Plugin:
    name: str
    version: str
    plugin_type: PluginType
    capabilities: PluginCapabilities = field(default_factory=PluginCapabilities)

    def __init__(
        self,
        name: str,
        version: str = "0.1.0",
        plugin_type: PluginType = PluginType.ANALYZER,
        capabilities: PluginCapabilities | None = None,
    ) -> None:
        self.name = name
        self.version = version
        self.plugin_type = plugin_type
        self.capabilities = capabilities or PluginCapabilities()

    def initialize(self) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def validate(self) -> list[str]:
        return []

    def metadata(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "type": self.plugin_type.name,
            "capabilities": {
                "parallel_safe": self.capabilities.parallel_safe,
                "streaming": self.capabilities.streaming,
                "incremental": self.capabilities.incremental,
                "resumable": self.capabilities.resumable,
                "bounded_memory": self.capabilities.bounded_memory,
                "supports_batch": self.capabilities.supports_batch,
            },
        }
