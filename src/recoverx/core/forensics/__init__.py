"""Forensic analysis framework for RecoverX.

Provides unified event abstraction, timeline construction,
artifact extraction, cross-source correlation, indexing,
query engine, case management, and reporting for forensic
investigations.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("recoverx")

FORENSIC_REGISTRY: dict[str, dict[str, Any]] = {
    "sources": {},
    "query_engines": {},
    "index_backends": {},
    "artifact_providers": {},
    "report_exporters": {},
}


def register_forensic_source(name: str, source_cls: Any, description: str = "") -> None:
    FORENSIC_REGISTRY["sources"][name] = {
        "class": source_cls,
        "description": description,
    }
    logger.debug("Forensic source registered: %s", name)


def register_query_engine(name: str, engine_cls: Any, description: str = "") -> None:
    FORENSIC_REGISTRY["query_engines"][name] = {
        "class": engine_cls,
        "description": description,
    }
    logger.debug("Query engine registered: %s", name)


def register_index_backend(name: str, backend_cls: Any, description: str = "") -> None:
    FORENSIC_REGISTRY["index_backends"][name] = {
        "class": backend_cls,
        "description": description,
    }
    logger.debug("Index backend registered: %s", name)


def register_artifact_provider(name: str, provider_cls: Any, description: str = "") -> None:
    FORENSIC_REGISTRY["artifact_providers"][name] = {
        "class": provider_cls,
        "description": description,
    }
    logger.debug("Artifact provider registered: %s", name)


def register_report_exporter(name: str, format_name: str, description: str = "") -> None:
    FORENSIC_REGISTRY["report_exporters"][name] = {
        "format": format_name,
        "description": description,
    }
    logger.debug("Report exporter registered: %s (%s)", name, format_name)


def get_forensic_source(name: str) -> dict[str, Any] | None:
    return FORENSIC_REGISTRY["sources"].get(name)


def list_forensic_sources() -> list[str]:
    return list(FORENSIC_REGISTRY["sources"].keys())


def list_index_backends() -> list[str]:
    return list(FORENSIC_REGISTRY["index_backends"].keys())


def list_exporters() -> list[str]:
    return list(FORENSIC_REGISTRY["report_exporters"].keys())
