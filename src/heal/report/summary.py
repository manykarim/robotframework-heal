"""Machine-readable run summary + GitHub annotations from the run store."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from ..core.schemas import HealEvent, OutcomeStatus


def build_summary(events: list[HealEvent]) -> dict:
    by_status = Counter(e.outcome.status.value for e in events if e.outcome)
    by_class = Counter(
        e.outcome.diagnosis.failure_class.value for e in events if e.outcome
    )
    files = sorted({e.source for e in events if e.source})
    total_tokens = sum(e.outcome.usage.total_tokens for e in events if e.outcome)
    fixes = [e.fix_proposal for e in events if e.fix_proposal]
    return {
        "transactions": len(events),
        "healed": by_status.get(OutcomeStatus.HEALED.value, 0),
        "unhealed": by_status.get(OutcomeStatus.UNHEALED.value, 0),
        "suppressed": by_status.get(OutcomeStatus.SUPPRESSED.value, 0),
        "by_failure_class": dict(by_class),
        "affected_files": files,
        "total_tokens": total_tokens,
        "fix_proposals": {
            "total": len(fixes),
            "local": sum(1 for f in fixes if f.blast_radius.value == "local"),
            "shared": sum(1 for f in fixes if f.blast_radius.value == "shared"),
        },
    }


def write_summary(events: list[HealEvent], path: str | Path) -> dict:
    summary = build_summary(events)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def gha_annotations(events: list[HealEvent]) -> list[str]:
    """GitHub workflow-command annotations (one per transaction)."""
    lines = []
    for event in events:
        if not event.outcome or not event.rca:
            continue
        level = "warning" if event.outcome.status is OutcomeStatus.HEALED else "error"
        location = ""
        if event.source:
            location = f" file={event.source}" + (f",line={event.lineno}" if event.lineno else "")
        message = event.rca.clean_message.replace("\n", " ")
        lines.append(f"::{level}{location}::{message}")
    return lines
