from __future__ import annotations

import logging
from typing import Any

from .base import Plugin
from .registry import PluginRegistry

logger = logging.getLogger("recoverx")


class PluginLifecycle:
    def __init__(self, registry: PluginRegistry) -> None:
        self._registry = registry
        self._initialized: set[str] = set()

    def initialize_all(self) -> list[str]:
        errors: list[str] = []
        for plugin in list(self._registry._plugins.values()):
            try:
                plugin.initialize()
                self._initialized.add(plugin.name)
            except Exception as e:
                logger.error("Failed to initialize plugin %s: %s", plugin.name, e)
                errors.append(plugin.name)
        return errors

    def shutdown_all(self) -> None:
        for name in list(self._initialized):
            plugin = self._registry.get(name)
            if plugin:
                try:
                    plugin.shutdown()
                except Exception as e:
                    logger.error("Error shutting down plugin %s: %s", name, e)
        self._initialized.clear()

    def validate_all(self) -> dict[str, list[str]]:
        results: dict[str, list[str]] = {}
        for plugin in self._registry._plugins.values():
            issues = plugin.validate()
            if issues:
                results[plugin.name] = issues
        return results

    def is_initialized(self, name: str) -> bool:
        return name in self._initialized

    def __enter__(self) -> PluginLifecycle:
        self.initialize_all()
        return self

    def __exit__(self, *args: object) -> None:
        self.shutdown_all()
