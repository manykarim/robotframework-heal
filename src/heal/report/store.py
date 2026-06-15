"""Append-only JSONL run store: one line per healing transaction, written at
transaction end — a crashed run loses nothing already recorded.

Merging supports `--rerunfailed`: events for the same source location are
deduplicated keeping the latest outcome (later file/line wins).
"""

from __future__ import annotations

from pathlib import Path

from ..core.schemas import HealEvent

EVENTS_FILENAME = "events.jsonl"


class RunStore:
    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self.path = self.directory / EVENTS_FILENAME

    def append(self, event: HealEvent) -> None:
        """Write one event durably (open-write-close per event, crash-safe)."""
        self.directory.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(event.to_jsonl() + "\n")
            f.flush()

    def load(self) -> list[HealEvent]:
        return load_events(self.path)


def load_events(path: str | Path) -> list[HealEvent]:
    """Load events, skipping corrupt/truncated lines (crash tolerance)."""
    path = Path(path)
    if not path.is_file():
        return []
    events: list[HealEvent] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(HealEvent.from_jsonl(line))
        except Exception:
            continue  # truncated tail from a crash mid-write
    return events


def dedupe_key(event: HealEvent) -> tuple:
    return (event.source or "", event.lineno or 0, event.test_name, event.keyword.name if event.keyword else "")


def merge_events(*event_lists: list[HealEvent]) -> list[HealEvent]:
    """Merge runs (initial + rerun): same location keeps the LATEST event."""
    merged: dict[tuple, HealEvent] = {}
    for events in event_lists:
        for event in events:
            merged[dedupe_key(event)] = event
    return sorted(merged.values(), key=lambda e: (e.source or "", e.lineno or 0, e.test_name))
