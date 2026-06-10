"""Run-level usage accounting and budget enforcement.

The ledger accumulates tokens/requests across ALL transactions in a run
(agents are reused, so per-agent limits alone cannot bound a run). Budget
breaches never abort the test run — the engine degrades to RCA-only mode.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from pydantic_ai.usage import RunUsage, UsageLimits

from .settings import HealSettings


@dataclass
class TransactionBudget:
    """Budget view for one healing transaction."""

    started_at: float
    max_seconds: float
    usage_limits: UsageLimits

    def remaining_seconds(self) -> float:
        return max(0.0, self.max_seconds - (time.monotonic() - self.started_at))

    def exhausted(self) -> bool:
        return self.remaining_seconds() <= 0.0


@dataclass
class RunLedger:
    """Thread-safe run-wide usage accounting (healer loop + main thread)."""

    settings: HealSettings
    total_tokens: int = 0
    total_requests: int = 0
    transactions: int = 0
    healed: int = 0
    unhealed: int = 0
    suppressed: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def begin_transaction(self) -> TransactionBudget:
        with self._lock:
            self.transactions += 1
        return TransactionBudget(
            started_at=time.monotonic(),
            max_seconds=self.settings.max_failure_seconds,
            usage_limits=UsageLimits(
                request_limit=self.settings.request_limit,
                total_tokens_limit=self.settings.max_failure_tokens,
            ),
        )

    def record_usage(self, usage: RunUsage | None) -> None:
        if usage is None:
            return
        with self._lock:
            self.total_tokens += usage.total_tokens or 0
            self.total_requests += usage.requests or 0

    def record_outcome(self, status: str) -> None:
        with self._lock:
            if status == "healed":
                self.healed += 1
            elif status == "unhealed":
                self.unhealed += 1
            else:
                self.suppressed += 1

    def run_budget_exhausted(self) -> bool:
        """True once the run-wide token cap is breached -> degrade to RCA-only."""
        with self._lock:
            return self.total_tokens >= self.settings.max_run_tokens

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                "total_tokens": self.total_tokens,
                "total_requests": self.total_requests,
                "transactions": self.transactions,
                "healed": self.healed,
                "unhealed": self.unhealed,
                "suppressed": self.suppressed,
            }
