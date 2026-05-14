"""Scanner registry for RecoverX.

Central registry for all scanning backends.
Enables dynamic selection and future plugin loading.
"""

from __future__ import annotations

import logging

from recoverx.core.utils.raw_reader import RawReader

logger = logging.getLogger("recoverx")

SCANNER_REGISTRY: dict[str, type] = {}


def register_scanner(name: str, scanner_cls: type) -> None:
    """Register a scanner backend for dynamic loading."""
    SCANNER_REGISTRY[name] = scanner_cls
    logger.debug("Scanner registered: %s -> %s", name, scanner_cls.__name__)


def get_scanner(name: str) -> type | None:
    """Get a scanner class by name."""
    return SCANNER_REGISTRY.get(name)


def list_scanners() -> list[str]:
    """List all registered scanner names."""
    return list(SCANNER_REGISTRY.keys())


def detect_scanner(reader: RawReader) -> str:
    """Auto-detect best scanner for the given source."""
    if reader.size > 1024 * 1024 * 1024:
        return "streaming"
    return "threaded"
