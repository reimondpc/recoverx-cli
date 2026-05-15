from __future__ import annotations

from datetime import datetime
from typing import Any

from .models import Confidence, EventSource, EventType, ForensicEvent


def make_event(
    event_type: EventType,
    source: EventSource,
    timestamp: datetime | None = None,
    filename: str = "",
    parent_name: str = "",
    mft_reference: int = 0,
    parent_mft_reference: int = 0,
    file_size: int = 0,
    confidence: float = Confidence.MEDIUM.value,
    previous_filename: str = "",
    notes: list[str] | None = None,
    **kwargs: Any,
) -> ForensicEvent:
    return ForensicEvent(
        timestamp=timestamp,
        event_type=event_type,
        source=source,
        filename=filename,
        parent_name=parent_name,
        mft_reference=mft_reference,
        parent_mft_reference=parent_mft_reference,
        file_size=file_size,
        confidence=confidence,
        previous_filename=previous_filename,
        notes=notes or [],
        attributes=kwargs,
    )


def file_created(
    timestamp: datetime | None,
    filename: str,
    mft_reference: int = 0,
    parent_mft_reference: int = 0,
    file_size: int = 0,
    source: EventSource = EventSource.MFT,
    **kwargs: Any,
) -> ForensicEvent:
    return make_event(
        EventType.FILE_CREATED,
        source,
        timestamp,
        filename=filename,
        mft_reference=mft_reference,
        parent_mft_reference=parent_mft_reference,
        file_size=file_size,
        confidence=Confidence.HIGH.value,
        **kwargs,
    )


def file_deleted(
    timestamp: datetime | None,
    filename: str,
    mft_reference: int = 0,
    parent_mft_reference: int = 0,
    source: EventSource = EventSource.MFT,
    **kwargs: Any,
) -> ForensicEvent:
    return make_event(
        EventType.FILE_DELETED,
        source,
        timestamp,
        filename=filename,
        mft_reference=mft_reference,
        parent_mft_reference=parent_mft_reference,
        confidence=Confidence.HIGH.value,
        **kwargs,
    )


def file_modified(
    timestamp: datetime | None,
    filename: str,
    mft_reference: int = 0,
    file_size: int = 0,
    source: EventSource = EventSource.MFT,
    **kwargs: Any,
) -> ForensicEvent:
    return make_event(
        EventType.FILE_MODIFIED,
        source,
        timestamp,
        filename=filename,
        mft_reference=mft_reference,
        file_size=file_size,
        confidence=Confidence.HIGH.value,
        **kwargs,
    )


def file_renamed(
    timestamp: datetime | None,
    old_name: str,
    new_name: str,
    mft_reference: int = 0,
    parent_mft_reference: int = 0,
    source: EventSource = EventSource.USN,
    **kwargs: Any,
) -> ForensicEvent:
    return make_event(
        EventType.FILE_RENAMED,
        source,
        timestamp,
        filename=new_name,
        previous_filename=old_name,
        mft_reference=mft_reference,
        parent_mft_reference=parent_mft_reference,
        confidence=Confidence.HIGH.value,
        **kwargs,
    )


def attribute_changed(
    timestamp: datetime | None,
    filename: str,
    mft_reference: int = 0,
    attribute_type: str = "",
    source: EventSource = EventSource.MFT,
    **kwargs: Any,
) -> ForensicEvent:
    return make_event(
        EventType.ATTRIBUTE_CHANGED,
        source,
        timestamp,
        filename=filename,
        mft_reference=mft_reference,
        confidence=Confidence.MEDIUM.value,
        attribute_type=attribute_type,
        **kwargs,
    )
