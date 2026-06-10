"""HealSession: what a failure-class plugin may do to the world.

The engine hands plugins a session instead of raw driver/RF access so the
same plugins work under the RF listener (calls marshalled to the main
thread), the CLI (no rerun capability) and tests (fakes).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .schemas import KeywordCall


class RerunNotSupported(RuntimeError):
    """Raised by sessions that cannot re-execute keywords (e.g. post-run CLI)."""


@runtime_checkable
class HealSession(Protocol):
    @property
    def driver(self) -> Any:
        """SessionDriver for the failing library (duck-typed in core)."""
        ...

    def rerun_keyword(self, keyword: KeywordCall, *, locator_override: str | None = None) -> Any:
        """Re-execute the keyword (optionally with a replaced locator).

        Returns the keyword's return value; raises on keyword failure;
        raises RerunNotSupported when the surface cannot rerun.
        """
        ...
