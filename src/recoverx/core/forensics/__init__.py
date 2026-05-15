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
    "analyzers": {},
    "plugins": {},
    "exporters": {},
    "distributed_workers": {},
    "acquisition_providers": {},
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


def register_analyzer(name: str, analyzer_cls: Any, description: str = "") -> None:
    FORENSIC_REGISTRY["analyzers"][name] = {
        "class": analyzer_cls,
        "description": description,
    }
    logger.debug("Analyzer registered: %s", name)


def register_plugin(name: str, plugin_cls: Any, description: str = "") -> None:
    FORENSIC_REGISTRY["plugins"][name] = {
        "class": plugin_cls,
        "description": description,
    }
    logger.debug("Plugin registered: %s", name)


def register_exporter(name: str, exporter_cls: Any, description: str = "") -> None:
    FORENSIC_REGISTRY["exporters"][name] = {
        "class": exporter_cls,
        "description": description,
    }
    logger.debug("Exporter registered: %s", name)


def register_distributed_worker(name: str, worker_cls: Any, description: str = "") -> None:
    FORENSIC_REGISTRY["distributed_workers"][name] = {
        "class": worker_cls,
        "description": description,
    }
    logger.debug("Distributed worker registered: %s", name)


def register_acquisition_provider(name: str, provider_cls: Any, description: str = "") -> None:
    FORENSIC_REGISTRY["acquisition_providers"][name] = {
        "class": provider_cls,
        "description": description,
    }
    logger.debug("Acquisition provider registered: %s", name)


def get_forensic_source(name: str) -> dict[str, Any] | None:
    return FORENSIC_REGISTRY["sources"].get(name)


def list_forensic_sources() -> list[str]:
    return list(FORENSIC_REGISTRY["sources"].keys())


def list_index_backends() -> list[str]:
    return list(FORENSIC_REGISTRY["index_backends"].keys())


def list_exporters() -> list[str]:
    return list(FORENSIC_REGISTRY["report_exporters"].keys())


def list_analyzers() -> list[str]:
    return list(FORENSIC_REGISTRY["analyzers"].keys())


def list_plugins() -> list[str]:
    return list(FORENSIC_REGISTRY["plugins"].keys())


def list_distributed_workers() -> list[str]:
    return list(FORENSIC_REGISTRY["distributed_workers"].keys())


def list_acquisition_providers() -> list[str]:
    return list(FORENSIC_REGISTRY["acquisition_providers"].keys())
