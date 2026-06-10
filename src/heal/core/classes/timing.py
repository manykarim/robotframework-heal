"""Timing failure class: page not ready / still loading. Heal = wait + rerun (no LLM)."""

from __future__ import annotations

import asyncio
import time

from ..schemas import (
    ActionType,
    Attempt,
    Confidence,
    Diagnosis,
    FailureClass,
    FailureContext,
    HealAction,
    HealOutcome,
    OutcomeStatus,
)
from ..session import HealSession, RerunNotSupported
from .base import FailureClassPlugin


class TimingPlugin(FailureClassPlugin):
    failure_class = FailureClass.TIMING

    def detect(self, ctx: FailureContext, session: HealSession) -> Diagnosis | None:
        driver = session.driver
        if driver is None:
            return None
        if not driver.is_page_ready():
            return Diagnosis(
                failure_class=FailureClass.TIMING,
                confidence=Confidence.HIGH,
                rationale="document.readyState is not 'complete' — the page is still loading.",
            )
        return None

    async def heal(self, ctx, session, runtime, budget, diagnosis) -> HealOutcome:
        start = time.monotonic()
        timeout = min(runtime.settings.ready_timeout_seconds, budget.remaining_seconds())
        ready = await asyncio.to_thread(_wait_ready, session, timeout)
        waited = time.monotonic() - start
        wait_attempt = Attempt(
            action=HealAction(
                type=ActionType.WAIT,
                description=f"waited {waited:.1f}s for page-ready (timeout {timeout:.0f}s)",
                params={"waited_seconds": f"{waited:.1f}"},
            ),
            succeeded=ready,
        )
        if not ready:
            return HealOutcome(
                status=OutcomeStatus.UNHEALED,
                diagnosis=diagnosis,
                attempts=[wait_attempt],
                detail=f"Page did not reach ready state within {timeout:.0f}s.",
            )
        try:
            return_value = await asyncio.to_thread(session.rerun_keyword, ctx.keyword)
        except RerunNotSupported:
            return HealOutcome(
                status=OutcomeStatus.UNHEALED, diagnosis=diagnosis, attempts=[wait_attempt],
                detail="Page became ready but this surface cannot rerun keywords.",
            )
        except Exception as exc:
            rerun_attempt = Attempt(
                action=HealAction(type=ActionType.RERUN, description="rerun after page-ready"),
                succeeded=False,
                detail=f"{type(exc).__name__}: {exc}"[:300],
            )
            return HealOutcome(
                status=OutcomeStatus.UNHEALED, diagnosis=diagnosis,
                attempts=[wait_attempt, rerun_attempt],
                detail="Rerun still failed after the page became ready.",
            )
        return HealOutcome(
            status=OutcomeStatus.HEALED,
            diagnosis=diagnosis,
            attempts=[wait_attempt, Attempt(action=HealAction(type=ActionType.RERUN, description="rerun after page-ready"), succeeded=True)],
            return_value_repr=repr(return_value) if return_value is not None else None,
            detail=f"Healed by waiting {waited:.1f}s for the page to finish loading.",
        )


def _wait_ready(session: HealSession, timeout: float) -> bool:
    return bool(session.driver.wait_until_ready(timeout))
