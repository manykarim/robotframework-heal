"""Overlay failure class: an open dialog/overlay blocks the interaction.

Detection is deterministic (open dialog present while the target exists).
Healing (dismiss + verify + rerun) is implemented in phase 6 (task 6.3).
"""

from __future__ import annotations

from ..schemas import Confidence, Diagnosis, FailureClass, FailureContext
from ..session import HealSession
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
