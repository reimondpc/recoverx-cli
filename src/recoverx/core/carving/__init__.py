"""Carving engine for RecoverX.

Central registry for all file carvers.
Supports dynamic loading and future plugin discovery.
"""

from __future__ import annotations

import logging

from recoverx.core.carving.base import BaseCarver

logger = logging.getLogger("recoverx")

CARVER_REGISTRY: dict[str, type[BaseCarver]] = {}


def register_carver(name: str, carver_cls: type[BaseCarver]) -> None:
    """Register a carver for dynamic loading."""
    CARVER_REGISTRY[name] = carver_cls
    logger.debug("Carver registered: %s -> %s", name, carver_cls.__name__)


def get_carver(name: str) -> type[BaseCarver] | None:
    """Get a carver class by name."""
    return CARVER_REGISTRY.get(name)


def list_carvers() -> list[str]:
    return list(CARVER_REGISTRY.keys())
