"""Locator-drift failure class: the locator matches nothing on the live page.

Detection is deterministic (count == 0). Healing (agentic proposal +
verification + rerun) is implemented in phase 4 (task 4.3).
"""

from __future__ import annotations

from ..schemas import Confidence, Diagnosis, EvidenceKind, FailureClass, FailureContext
from ..session import HealSession
from .base import FailureClassPlugin


class LocatorDriftPlugin(FailureClassPlugin):
    failure_class = FailureClass.LOCATOR_DRIFT
    heal_evidence = (EvidenceKind.DOM_EXCERPT,)

    def detect(self, ctx: FailureContext, session: HealSession) -> Diagnosis | None:
        if not ctx.failed_locator or session.driver is None:
            return None
        if session.driver.count(ctx.failed_locator) == 0:
            return Diagnosis(
                failure_class=FailureClass.LOCATOR_DRIFT,
                confidence=Confidence.HIGH,
                rationale=f"Locator {ctx.failed_locator!r} matches 0 elements on the live page.",
            )
        return None
