"""Runlist engine for NTFS non-resident data recovery.

Provides mapping (VCN→LCN translation), execution (disk image reading),
sparse region handling, and validation for NTFS data runs.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("recoverx")

RUNLIST_COMPONENTS: dict[str, dict[str, Any]] = {}


def register_component(name: str, module: object, description: str = "") -> None:
    """Register a runlist engine component."""
    RUNLIST_COMPONENTS[name] = {
        "module": module,
        "description": description,
    }
    logger.debug("Runlist component registered: %s", name)


def get_component(name: str) -> dict[str, Any] | None:
    """Get a registered runlist component by name."""
    return RUNLIST_COMPONENTS.get(name)


def list_components() -> list[str]:
    """List all registered runlist component names."""
    return list(RUNLIST_COMPONENTS.keys())
