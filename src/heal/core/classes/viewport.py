"""Viewport failure class: element exists but is outside the visible viewport.

Detection is deterministic. Healing (scroll/swipe into view + rerun) is
implemented in phase 6 (task 6.2).
"""

from __future__ import annotations

from ..schemas import Confidence, Diagnosis, FailureClass, FailureContext
from ..session import HealSession
from .base import FailureClassPlugin


class ViewportPlugin(FailureClassPlugin):
    failure_class = FailureClass.VIEWPORT

    def detect(self, ctx: FailureContext, session: HealSession) -> Diagnosis | None:
        driver = session.driver
        if not ctx.failed_locator or driver is None:
            return None
        if driver.count(ctx.failed_locator) == 0:
            return None  # not present at all -> locator-drift territory
        in_viewport = driver.is_in_viewport(ctx.failed_locator)
        if in_viewport is False:
            return Diagnosis(
                failure_class=FailureClass.VIEWPORT,
                confidence=Confidence.HIGH,
                rationale=f"Element {ctx.failed_locator!r} exists but is outside the visible viewport.",
            )
        return None
