"""Artifact abstraction layer for forensic investigation.

Provides unified artifact types that wrap raw forensic data
(events, files, journal entries) into self-contained evidence
objects with unique IDs, confidence scores, source tracking,
and metadata.
"""

from __future__ import annotations

from .models import (
    Artifact,
    DeletedArtifact,
    FileArtifact,
    HashArtifact,
    JournalArtifact,
    TimelineArtifact,
)

__all__ = [
    "Artifact",
    "FileArtifact",
    "TimelineArtifact",
    "JournalArtifact",
    "DeletedArtifact",
    "HashArtifact",
]
