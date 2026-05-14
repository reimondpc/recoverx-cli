"""Reporting registry for RecoverX.

Central registry for all report generators.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("recoverx")

REPORT_REGISTRY: dict[str, type] = {}


def register_report(name: str, report_cls: type) -> None:
    """Register a report generator for dynamic loading."""
    REPORT_REGISTRY[name] = report_cls
    logger.debug("Report registered: %s -> %s", name, report_cls.__name__)


def get_report(name: str) -> type | None:
    """Get a report class by name."""
    return REPORT_REGISTRY.get(name)


def list_reports() -> list[str]:
    return list(REPORT_REGISTRY.keys())
