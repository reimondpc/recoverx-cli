"""Filesystem registry for RecoverX.

Central registry for all filesystem parsers.
Enables dynamic selection and future plugin loading.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("recoverx")

FILESYSTEM_REGISTRY: dict[str, type] = {}


def register_filesystem(name: str, fs_cls: type) -> None:
    """Register a filesystem parser for dynamic loading."""
    FILESYSTEM_REGISTRY[name] = fs_cls
    logger.debug("Filesystem registered: %s -> %s", name, fs_cls.__name__)


def get_filesystem(name: str) -> type | None:
    """Get a filesystem parser class by name."""
    return FILESYSTEM_REGISTRY.get(name)


def list_filesystems() -> list[str]:
    """List all registered filesystem names."""
    return list(FILESYSTEM_REGISTRY.keys())
