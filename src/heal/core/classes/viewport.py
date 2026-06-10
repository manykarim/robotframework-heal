"""Viewport failure class: the element exists but is not scrolled into sight.

Web: element in DOM, outside viewport -> scroll into view + rerun (no LLM).
Mobile (drivers with `dom_covers_viewport_only`): an off-screen element is
ABSENT from the page source, so detection fires on count==0 and healing is a
bounded swipe search; if the element truly doesn't exist, the outcome falls
through to locator-drift healing (single engine hop).
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


def _viewport_limited(driver) -> bool:
    return bool(getattr(driver, "dom_covers_viewport_only", False))


class ViewportPlugin(FailureClassPlugin):
    failure_class = FailureClass.VIEWPORT

    def detect(self, ctx: FailureContext, session: HealSession) -> Diagnosis | None:
        driver = session.driver
        if not ctx.failed_locator or driver is None:
            return None
        count = driver.count(ctx.failed_locator)
        if count == 0:
            if _viewport_limited(driver):
                return Diagnosis(
                    failure_class=FailureClass.VIEWPORT,
                    confidence=Confidence.MEDIUM,
                    rationale=(
                        f"Element {ctx.failed_locator!r} is absent from the current screen "
                        "hierarchy; it may be off-screen (swipe search) or renamed."
                    ),
                )
            return None  # web: not present at all -> locator-drift territory
        if driver.is_in_viewport(ctx.failed_locator) is False:
            return Diagnosis(
                failure_class=FailureClass.VIEWPORT,
                confidence=Confidence.HIGH,
                rationale=f"Element {ctx.failed_locator!r} exists but is outside the visible viewport.",
            )
        return None

    async def heal(self, ctx, session, runtime, budget, diagnosis) -> HealOutcome:
        driver = session.driver
        locator = ctx.failed_locator or ""
        action_name = "swipe search" if _viewport_limited(driver) else "scroll into view"
        found = await asyncio.to_thread(driver.scroll_into_view, locator)
        scroll_attempt = Attempt(
            action=HealAction(
                type=ActionType.SWIPE if _viewport_limited(driver) else ActionType.SCROLL,
                description=f"{action_name} for {locator!r}",
            ),
            succeeded=bool(found),
        )
        if not found:
            return HealOutcome(
                status=OutcomeStatus.UNHEALED,
                diagnosis=diagnosis,
                attempts=[scroll_attempt],
                detail=f"Element not reachable by {action_name}.",
                # on mobile the element may simply have been renamed
                fallthrough_to=FailureClass.LOCATOR_DRIFT if _viewport_limited(driver) else None,
            )
        try:
            return_value = await asyncio.to_thread(session.rerun_keyword, ctx.keyword)
        except RerunNotSupported:
            return HealOutcome(
                status=OutcomeStatus.UNHEALED, diagnosis=diagnosis, attempts=[scroll_attempt],
                detail="Element brought into view but this surface cannot rerun keywords.",
            )
        except Exception as exc:
            return HealOutcome(
                status=OutcomeStatus.UNHEALED,
                diagnosis=diagnosis,
                attempts=[
                    scroll_attempt,
                    Attempt(
                        action=HealAction(type=ActionType.RERUN, description="rerun after scroll"),
                        succeeded=False,
                        detail=f"{type(exc).__name__}: {exc}"[:300],
                    ),
                ],
                detail="Rerun still failed after bringing the element into view.",
            )
        return HealOutcome(
            status=OutcomeStatus.HEALED,
            diagnosis=diagnosis,
            attempts=[
                scroll_attempt,
                Attempt(action=HealAction(type=ActionType.RERUN, description="rerun after scroll"), succeeded=True),
            ],
            return_value_repr=repr(return_value) if return_value is not None else None,
            detail=f"Healed by {action_name} and rerun.",
        )
