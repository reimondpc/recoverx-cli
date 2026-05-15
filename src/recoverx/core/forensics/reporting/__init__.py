"""Forensic reporting module with CSV, JSON, and Markdown export."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from io import StringIO
from typing import Any

from recoverx.core.forensics.models import ForensicEvent


def events_to_csv(events: list[ForensicEvent]) -> str:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "timestamp",
            "event_type",
            "source",
            "filename",
            "previous_filename",
            "mft_reference",
            "parent_mft_reference",
            "file_size",
            "confidence",
            "notes",
            "lsn",
            "usn_reason_flags",
        ]
    )
    for e in events:
        writer.writerow(
            [
                e.timestamp.isoformat() if e.timestamp else "",
                e.event_type.value,
                e.source.value,
                e.filename,
                e.previous_filename,
                str(e.mft_reference),
                str(e.parent_mft_reference),
                str(e.file_size),
                f"{e.confidence:.2f}",
                "; ".join(e.notes),
                str(e.lsn),
                ",".join(e.usn_reason_flags),
            ]
        )
    return output.getvalue()


def events_to_json(events: list[ForensicEvent], indent: int = 2) -> str:
    return json.dumps(
        {
            "report_type": "forensic_timeline",
            "generated_at": datetime.now().isoformat(),
            "total_events": len(events),
            "events": [e.to_dict() for e in events],
        },
        indent=indent,
    )


def events_to_markdown(events: list[ForensicEvent], title: str = "Forensic Timeline Report") -> str:
    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().isoformat()}")
    lines.append(f"**Total events:** {len(events)}")
    lines.append("")

    if not events:
        lines.append("_No events to report._")
        return "\n".join(lines)

    lines.append("| Timestamp | Event | File | Source | Confidence | Notes |")
    lines.append("|-----------|-------|------|--------|------------|-------|")

    for e in events:
        ts = e.timestamp.isoformat() if e.timestamp else "N/A"
        fname = e.filename or "N/A"
        if e.previous_filename:
            fname = f"{e.previous_filename} -> {fname}"
        notes_escaped = "; ".join(e.notes).replace("|", "\\|")
        lines.append(
            f"| {ts} | {e.event_type.value} | {fname}"
            f" | {e.source.value} | {e.confidence:.2f} | {notes_escaped} |"
        )

    lines.append("")
    return "\n".join(lines)


def investigation_summary(events: list[ForensicEvent]) -> dict[str, Any]:
    from collections import Counter

    type_counts = Counter(e.event_type.value for e in events)
    source_counts = Counter(e.source.value for e in events)
    deleted = [e for e in events if e.event_type.value == "FILE_DELETED"]
    created = [e for e in events if e.event_type.value == "FILE_CREATED"]
    renamed = [e for e in events if e.event_type.value == "FILE_RENAMED"]

    timestamps = [e.timestamp for e in events if e.timestamp]

    return {
        "total_events": len(events),
        "unique_files": len({e.filename for e in events if e.filename}),
        "by_type": dict(type_counts),
        "by_source": dict(source_counts),
        "deleted_count": len(deleted),
        "created_count": len(created),
        "renamed_count": len(renamed),
        "time_range_start": min(timestamps).isoformat() if timestamps else None,
        "time_range_end": max(timestamps).isoformat() if timestamps else None,
        "deleted_files": [e.filename for e in deleted if e.filename],
        "rename_chains": _extract_rename_chains(events),
    }


def correlation_report(events: list[ForensicEvent]) -> dict[str, Any]:
    correlated = [e for e in events if e.source.value in ("CORRELATION",)]
    mft_usn = [e for e in events if "Correlated with MFT" in "; ".join(e.notes)]

    return {
        "total_correlated_events": len(correlated),
        "mft_usn_matches": len(mft_usn),
        "correlation_rate": f"{len(correlated) / max(len(events), 1) * 100:.1f}%",
        "by_type": _count_by((e for e in correlated), "event_type"),
    }


def _count_by(events: Any, attr: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for e in events:
        val = getattr(e, attr, "unknown")
        key = val.value if hasattr(val, "value") else str(val)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _extract_rename_chains(events: list[ForensicEvent]) -> list[dict[str, Any]]:
    by_mft: dict[int, list[ForensicEvent]] = {}
    for e in events:
        if e.mft_reference > 0 and e.event_type.value == "FILE_RENAMED":
            by_mft.setdefault(e.mft_reference, []).append(e)

    chains: list[dict[str, Any]] = []
    for mft_ref, renames in by_mft.items():
        sorted_r = sorted(renames, key=lambda x: x.timestamp or datetime.min)
        chain = []
        for r in sorted_r:
            chain.append(
                {
                    "from": r.previous_filename or r.filename,
                    "to": r.filename,
                    "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                }
            )
        chains.append(
            {
                "mft_reference": mft_ref,
                "chain_length": len(chain),
                "events": chain,
            }
        )
    return chains
