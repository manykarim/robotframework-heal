"""Form-state failure class: action blocked by required/invalid form fields.

Diagnose-only by default: the product is an enriched error naming the fields
the test never filled. Vision (when configured) corroborates the DOM finding.
Auto-fill exists behind HEAL_FORM_FILL and records every value it enters —
it invents test data, so it is opt-in by design.
"""

from __future__ import annotations

import asyncio

from ..agents.vision import FormVerdict, ask_vision
from ..schemas import (
    ActionType,
    Attempt,
    Confidence,
    Diagnosis,
    EvidenceKind,
    FailureClass,
    FailureContext,
    HealAction,
    HealOutcome,
    OutcomeStatus,
)
from ..session import HealSession, RerunNotSupported
from .base import FailureClassPlugin

_FILL_VALUES = (
    ("email", "heal-test@example.com"),
    ("mail", "heal-test@example.com"),
    ("phone", "0123456789"),
    ("number", "1"),
    ("date", "2026-01-01"),
)


def _guess_value(field_name: str) -> str:
    lowered = field_name.lower()
    for marker, value in _FILL_VALUES:
        if marker in lowered:
            return value
    return "heal-test"


class FormStatePlugin(FailureClassPlugin):
    failure_class = FailureClass.FORM_STATE
    heal_evidence = (EvidenceKind.SCREENSHOT,)

    def detect(self, ctx: FailureContext, session: HealSession) -> Diagnosis | None:
        driver = session.driver
        if driver is None or not hasattr(driver, "find_form_issues"):
            return None
        # only explains failures on elements that exist (e.g. blocked submit)
        if ctx.failed_locator and driver.count(ctx.failed_locator) == 0:
            return None
        issues = driver.find_form_issues()
        if not issues:
            return None
        return Diagnosis(
            failure_class=FailureClass.FORM_STATE,
            confidence=Confidence.MEDIUM,
            rationale="; ".join(issues[:6]),
        )

    async def heal(self, ctx, session, runtime, budget, diagnosis) -> HealOutcome:
        driver = session.driver
        issues = await asyncio.to_thread(driver.find_form_issues)

        # vision corroboration (optional, degrades silently)
        screenshot = ctx.evidence_of(EvidenceKind.SCREENSHOT)
        vision_note = ""
        if screenshot and screenshot.path:
            from pathlib import Path

            png = Path(screenshot.path).read_bytes()
            verdict: FormVerdict | None = await ask_vision(
                runtime, FormVerdict,
                "Does this form screenshot show field validation errors? Name the fields.",
                png, budget.usage_limits,
            )
            if verdict and verdict.has_validation_error and verdict.error_fields:
                vision_note = f" Screenshot confirms errors on: {', '.join(verdict.error_fields[:5])}."

        issue_text = "; ".join(issues[:8]) or diagnosis.rationale
        if not runtime.settings.form_fill:
            return HealOutcome(
                status=OutcomeStatus.UNHEALED,
                diagnosis=diagnosis,
                detail=(
                    f"The action is blocked by form state: {issue_text}.{vision_note} "
                    "The test never filled these fields (set HEAL_FORM_FILL=true to "
                    "let heal enter placeholder values — it invents test data)."
                ),
            )

        # opt-in fill: enter recorded placeholder values into empty required fields
        attempts: list[Attempt] = []
        for issue in issues:
            if not issue.startswith("required field"):
                continue
            field_name = issue.split("'")[1]
            value = _guess_value(field_name)
            locator = f"[id='{field_name}'], [name='{field_name}']"
            attempt = Attempt(
                action=HealAction(
                    type=ActionType.FILL,
                    description=f"filled '{field_name}' with '{value}'",
                    params={"field": field_name, "value": value},
                ),
                succeeded=False,
            )
            try:
                await asyncio.to_thread(driver.fill_text, locator, value)
                attempt.succeeded = True
            except Exception as exc:
                attempt.detail = f"{type(exc).__name__}: {exc}"[:200]
            attempts.append(attempt)
        if not any(a.succeeded for a in attempts):
            return HealOutcome(
                status=OutcomeStatus.UNHEALED, diagnosis=diagnosis, attempts=attempts,
                detail=f"Form fill (opt-in) could not fill any field. {issue_text}",
            )
        try:
            return_value = await asyncio.to_thread(session.rerun_keyword, ctx.keyword)
        except (RerunNotSupported, Exception) as exc:  # noqa: B902
            attempts.append(
                Attempt(
                    action=HealAction(type=ActionType.RERUN, description="rerun after fill"),
                    succeeded=False,
                    detail=f"{type(exc).__name__}: {exc}"[:200],
                )
            )
            return HealOutcome(
                status=OutcomeStatus.UNHEALED, diagnosis=diagnosis, attempts=attempts,
                detail=f"Filled fields (values recorded) but the keyword still failed. {issue_text}",
            )
        attempts.append(
            Attempt(action=HealAction(type=ActionType.RERUN, description="rerun after fill"), succeeded=True)
        )
        return HealOutcome(
            status=OutcomeStatus.HEALED,
            diagnosis=diagnosis,
            attempts=attempts,
            return_value_repr=repr(return_value) if return_value is not None else None,
            detail=(
                "Healed by filling required fields with placeholder values (recorded in attempts). "
                "Fix the test to fill these fields explicitly."
            ),
        )
