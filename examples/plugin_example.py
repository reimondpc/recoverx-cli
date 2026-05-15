#!/usr/bin/env python3
"""Example RecoverX plugin: an AnalyzerPlugin that detects可疑 executable launches.

This plugin registers itself with the plugin system and can be loaded
via `recoverx plugins load` or used programmatically.

Usage:
    recoverx plugins load examples/plugin_example.py
    # or use the AnalyzerPlugin API directly
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from recoverx.core.forensics.models import EventType, ForensicEvent
from recoverx.plugins.base import PluginCapabilities, PluginType
from recoverx.plugins.interfaces import AnalyzerPlugin


class ExecutableLauncherDetector(AnalyzerPlugin):
    """Detects rapid executable creation events as potential malware droppers."""

    name = "exec-launcher-detector"
    version = "1.0.0"
    plugin_type = PluginType.ANALYZER
    capabilities = PluginCapabilities(
        parallel_safe=True,
        bounded_memory=True,
        supports_batch=True,
    )

    def __init__(self, window_seconds: int = 5, threshold: int = 3) -> None:
        super().__init__(self.name, self.version, self.plugin_type, self.capabilities)
        self.window_seconds = window_seconds
        self.threshold = threshold

    def initialize(self) -> None:
        print(
            f"[{self.name}] Initialized (window={self.window_seconds}s, "
            f"threshold={self.threshold})"
        )

    def shutdown(self) -> None:
        print(f"[{self.name}] Shutdown complete")

    def analyze(self, events: list[ForensicEvent]) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        exe_creations = [
            e
            for e in events
            if e.event_type == EventType.FILE_CREATED
            and (e.filename.endswith(".exe") or e.filename.endswith(".dll"))
        ]

        for i, ev in enumerate(exe_creations):
            if not ev.timestamp:
                continue
            window_start = ev.timestamp - timedelta(seconds=self.window_seconds)
            cluster = [
                e
                for e in exe_creations
                if e.timestamp and window_start <= e.timestamp <= ev.timestamp
            ]
            if len(cluster) >= self.threshold:
                findings.append(
                    {
                        "title": "Rapid executable creation burst",
                        "description": (
                            f"{len(cluster)} executables created in "
                            f"{self.window_seconds}s window"
                        ),
                        "severity": "HIGH",
                        "confidence": 0.85,
                        "mft_references": list({e.mft_reference for e in cluster}),
                        "filenames": [e.filename for e in cluster],
                        "timestamp": ev.timestamp.isoformat(),
                        "plugin": self.name,
                    }
                )

        return findings

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.window_seconds < 1:
            errors.append("window_seconds must be >= 1")
        if self.threshold < 2:
            errors.append("threshold must be >= 2")
        return errors

    def metadata(self) -> dict[str, Any]:
        base = super().metadata()
        base["config"] = {
            "window_seconds": self.window_seconds,
            "threshold": self.threshold,
        }
        return base


# Entry point for dynamic loading
plugin = ExecutableLauncherDetector()


if __name__ == "__main__":
    detector = ExecutableLauncherDetector()
    print(detector.metadata())
