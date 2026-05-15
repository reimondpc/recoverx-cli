"""Forensic analysis framework for RecoverX.

Provides unified event abstraction, timeline construction,
artifact extraction, and cross-source correlation for forensic
investigations across NTFS (MFT, USN, LogFile) and future filesystems.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("recoverx")

FORENSIC_REGISTRY: dict[str, dict[str, Any]] = {}


def register_forensic_source(name: str, source_cls: Any, description: str = "") -> None:
    FORENSIC_REGISTRY[name] = {
        "class": source_cls,
        "description": description,
    }
    logger.debug("Forensic source registered: %s", name)


def get_forensic_source(name: str) -> dict[str, Any] | None:
    return FORENSIC_REGISTRY.get(name)


def list_forensic_sources() -> list[str]:
    return list(FORENSIC_REGISTRY.keys())
