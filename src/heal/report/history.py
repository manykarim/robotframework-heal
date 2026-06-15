"""Cross-run healing history (SQLite): repeat-healing is a flakiness signal."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from ..core.schemas import HealEvent, OutcomeStatus

_SCHEMA = """
CREATE TABLE IF NOT EXISTS heal_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_at TEXT NOT NULL,
    source TEXT,
    lineno INTEGER,
    test_name TEXT,
    failure_class TEXT,
    status TEXT,
    failed_locator TEXT,
    healed_locator TEXT
);
CREATE INDEX IF NOT EXISTS idx_heal_history_locator
    ON heal_history (source, failed_locator);
"""


@dataclass(frozen=True)
class Hotspot:
    source: str
    failed_locator: str
    heal_count: int
    last_healed_at: str


class HealHistory:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def record(self, events: list[HealEvent]) -> None:
        rows = [
            (
                event.timestamp.isoformat(),
                event.source,
                event.lineno,
                event.test_name,
                event.outcome.diagnosis.failure_class.value if event.outcome else None,
                event.outcome.status.value if event.outcome else None,
                event.context.failed_locator if event.context else None,
                event.outcome.healed_locator if event.outcome else None,
            )
            for event in events
        ]
        with self._connect() as conn:
            conn.executemany(
                "INSERT INTO heal_history (recorded_at, source, lineno, test_name,"
                " failure_class, status, failed_locator, healed_locator)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )

    def hotspots(self, *, min_count: int = 3, days: int = 30) -> list[Hotspot]:
        """Locators healed at least `min_count` times within `days`."""
        query = """
            SELECT source, failed_locator, COUNT(*) AS n, MAX(recorded_at) AS last
            FROM heal_history
            WHERE status = ?
              AND failed_locator IS NOT NULL
              AND recorded_at >= datetime('now', ?)
            GROUP BY source, failed_locator
            HAVING n >= ?
            ORDER BY n DESC
        """
        with self._connect() as conn:
            rows = conn.execute(
                query, (OutcomeStatus.HEALED.value, f"-{days} days", min_count)
            ).fetchall()
        return [Hotspot(source=r[0] or "", failed_locator=r[1], heal_count=r[2], last_healed_at=r[3]) for r in rows]

    def recent_mappings(self, *, days: int = 30, limit: int = 500) -> list[tuple[str, str, str]]:
        """Recent healed (source, failed_locator, healed_locator) mappings,
        newest first, deduplicated per (source, failed_locator)."""
        query = """
            SELECT source, failed_locator, healed_locator, MAX(recorded_at)
            FROM heal_history
            WHERE status = ?
              AND failed_locator IS NOT NULL AND healed_locator IS NOT NULL
              AND recorded_at >= datetime('now', ?)
            GROUP BY source, failed_locator
            ORDER BY MAX(recorded_at) DESC
            LIMIT ?
        """
        with self._connect() as conn:
            rows = conn.execute(query, (OutcomeStatus.HEALED.value, f"-{days} days", limit)).fetchall()
        return [(r[0] or "", r[1], r[2]) for r in rows]

    def heal_count(self, source: str | None, failed_locator: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM heal_history WHERE source IS ? AND failed_locator = ? AND status = ?",
                (source, failed_locator, OutcomeStatus.HEALED.value),
            ).fetchone()
        return int(row[0])
