"""Overlay failure class: an open dialog/overlay blocks the interaction.

Healing is deterministic: the driver supplies dismiss-control candidates
(close/accept buttons inside the dialog); each is clicked and the dismissal
verified before the original keyword is rerun. No LLM in the default path.
"""

from __future__ import annotations

import asyncio

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


class OverlayPlugin(FailureClassPlugin):
    failure_class = FailureClass.OVERLAY

    def detect(self, ctx: FailureContext, session: HealSession) -> Diagnosis | None:
        driver = session.driver
        if driver is None:
            return None
        dialog = driver.open_dialog_locator()
        if dialog is None:
            return None
        # If the target is gone entirely, locator-drift should win; an open
        # dialog only explains failures on elements that are still present.
        if ctx.failed_locator and driver.count(ctx.failed_locator) == 0:
            return None
        return Diagnosis(
            failure_class=FailureClass.OVERLAY,
            confidence=Confidence.MEDIUM,
            rationale=f"An open dialog ({dialog}) likely intercepts the interaction.",
        )

    async def heal(self, ctx, session, runtime, budget, diagnosis) -> HealOutcome:
        driver = session.driver
        attempts: list[Attempt] = []
        candidates = await asyncio.to_thread(self._dismiss_candidates, driver)
        if not candidates:
            return HealOutcome(
                status=OutcomeStatus.UNHEALED, diagnosis=diagnosis,
                detail="No dismiss control could be identified for the open dialog.",
            )
        dismissed = False
        for candidate in candidates:
            attempt = Attempt(
                action=HealAction(type=ActionType.DISMISS, description=f"click {candidate!r}"),
                succeeded=False,
            )
            try:
                await asyncio.to_thread(driver.click, candidate)
                await asyncio.sleep(0.3)
                still_open = await asyncio.to_thread(driver.open_dialog_locator)
                attempt.succeeded = still_open is None
            except Exception as exc:
                attempt.detail = f"{type(exc).__name__}: {exc}"[:200]
            attempts.append(attempt)
            if attempt.succeeded:
                dismissed = True
                break
        if not dismissed:
            return HealOutcome(
                status=OutcomeStatus.UNHEALED, diagnosis=diagnosis, attempts=attempts,
                detail="Dialog could not be dismissed within candidate budget.",
            )
        try:
            return_value = await asyncio.to_thread(session.rerun_keyword, ctx.keyword)
        except RerunNotSupported:
            return HealOutcome(
                status=OutcomeStatus.UNHEALED, diagnosis=diagnosis, attempts=attempts,
                detail="Dialog dismissed but this surface cannot rerun keywords.",
            )
        except Exception as exc:
            attempts.append(
                Attempt(
                    action=HealAction(type=ActionType.RERUN, description="rerun after dismiss"),
                    succeeded=False,
                    detail=f"{type(exc).__name__}: {exc}"[:300],
                )
            )
            return HealOutcome(
                status=OutcomeStatus.UNHEALED, diagnosis=diagnosis, attempts=attempts,
                detail="Rerun still failed after dismissing the dialog.",
            )
        attempts.append(
            Attempt(action=HealAction(type=ActionType.RERUN, description="rerun after dismiss"), succeeded=True)
        )
        return HealOutcome(
            status=OutcomeStatus.HEALED,
            diagnosis=diagnosis,
            attempts=attempts,
            return_value_repr=repr(return_value) if return_value is not None else None,
            detail="Healed by dismissing the blocking dialog and rerunning.",
        )

    @staticmethod
    def _dismiss_candidates(driver) -> list[str]:
        finder = getattr(driver, "find_dismiss_controls", None)
        if finder is None:
            return []
        try:
            return list(finder())
        except Exception:
            return []
