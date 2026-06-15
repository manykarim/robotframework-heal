"""Assertion-drift failure class: expected value differs from the live UI.

Opt-in (`HEAL_ASSERTIONS`). The semantic guard refuses adjustments that change
the meaning of the assertion (different magnitude, different target) — those
are likely application defects and become RCA-only.
"""

from __future__ import annotations

import asyncio
import re

from ..agents.vision import AssertionVerdict, ask_vision
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

# RF assertion message shapes: "Text 'a' (str) should be 'b' (str)",
# "Text 'a' should be 'b'", "'a' != 'b'", "x (str) should be y (str)"
_PATTERNS = (
    re.compile(r"[Tt]ext '(?P<actual>.*?)' \(\w+\) should be '(?P<expected>.*?)' \(\w+\)"),
    re.compile(r"[Tt]ext '(?P<actual>.*?)' should be '(?P<expected>.*)'"),
    re.compile(r"'(?P<actual>.*?)' \(\w+\) should be '(?P<expected>.*?)' \(\w+\)"),
    re.compile(r"'(?P<actual>.*?)'\s*(?:!=|should be)\s*'(?P<expected>.*)'"),
    re.compile(r"(?P<actual>.+?) \(\w+\) should be (?P<expected>.+?) \(\w+\)"),
)

_NUMBER = re.compile(r"-?\d+(?:[.,]\d+)?")


def parse_assertion(message: str) -> tuple[str, str] | None:
    for pattern in _PATTERNS:
        match = pattern.search(message or "")
        if match:
            return match.group("actual"), match.group("expected")
    return None


def semantic_guard(expected: str, actual: str) -> str | None:
    """Return a refusal reason when the drift looks semantic, else None."""
    expected_nums = _NUMBER.findall(expected)
    actual_nums = _NUMBER.findall(actual)
    if expected_nums and actual_nums:
        try:
            e, a = float(expected_nums[0].replace(",", ".")), float(actual_nums[0].replace(",", "."))
            if e != 0 and a != 0 and (a / e >= 2 or e / a >= 2):
                return (
                    f"numeric magnitude differs ({expected_nums[0]} vs {actual_nums[0]}) — "
                    "likely an application defect, not assertion drift"
                )
        except ValueError:
            pass
    if expected and actual and not _similar(expected, actual):
        return "actual and expected share too little content — likely a different element or a defect"
    return None


def _similar(a: str, b: str) -> bool:
    a_words, b_words = set(a.lower().split()), set(b.lower().split())
    if not a_words or not b_words:
        return True
    return len(a_words & b_words) / min(len(a_words), len(b_words)) >= 0.3


class AssertionDriftPlugin(FailureClassPlugin):
    failure_class = FailureClass.ASSERTION_DRIFT
    heal_evidence = (EvidenceKind.SCREENSHOT,)

    def detect(self, ctx: FailureContext, session: HealSession) -> Diagnosis | None:
        parsed = parse_assertion(ctx.error_message)
        if parsed is None:
            return None
        actual, expected = parsed
        return Diagnosis(
            failure_class=FailureClass.ASSERTION_DRIFT,
            confidence=Confidence.MEDIUM,
            rationale=f"The UI shows {actual!r} but the test expects {expected!r}.",
        )

    async def heal(self, ctx, session, runtime, budget, diagnosis) -> HealOutcome:
        parsed = parse_assertion(ctx.error_message)
        if parsed is None:
            return HealOutcome(status=OutcomeStatus.UNHEALED, diagnosis=diagnosis,
                               detail="Could not parse expected/actual from the assertion message.")
        actual, expected = parsed

        if not runtime.settings.heal_assertions:
            return HealOutcome(
                status=OutcomeStatus.UNHEALED, diagnosis=diagnosis,
                detail=(
                    f"Assertion drift detected (expected {expected!r}, UI shows {actual!r}). "
                    "Assertion healing is disabled (set HEAL_ASSERTIONS=true to enable)."
                ),
            )

        refusal = semantic_guard(expected, actual)
        if refusal is not None:
            return HealOutcome(
                status=OutcomeStatus.UNHEALED,
                diagnosis=Diagnosis(
                    failure_class=FailureClass.UNKNOWN,
                    confidence=Confidence.MEDIUM,
                    rationale=f"Adjustment refused: {refusal}.",
                ),
                detail=f"Adjustment refused: {refusal}. Expected {expected!r}, actual {actual!r}.",
            )

        # optional vision corroboration that the on-screen value really is `actual`
        screenshot = ctx.evidence_of(EvidenceKind.SCREENSHOT)
        if screenshot and screenshot.path:
            from pathlib import Path

            verdict: AssertionVerdict | None = await ask_vision(
                runtime, AssertionVerdict,
                f"A test asserts the text {expected!r}. What does the corresponding element actually show? "
                "Is this a small wording drift (drift_confirmed) or a semantic/meaning change (semantic_change)?",
                Path(screenshot.path).read_bytes(), budget.usage_limits,
            )
            if verdict is not None and verdict.semantic_change:
                return HealOutcome(
                    status=OutcomeStatus.UNHEALED, diagnosis=diagnosis,
                    detail=f"Vision check judged the change semantic: {verdict.reason}",
                )

        # verified adjustment: rerun the verification keyword with the corrected expectation
        corrected_args = [actual if a == expected else a for a in ctx.keyword.args]
        if corrected_args == list(ctx.keyword.args):
            return HealOutcome(
                status=OutcomeStatus.UNHEALED, diagnosis=diagnosis,
                detail=f"Expected value {expected!r} not found among keyword arguments; cannot adjust safely.",
            )
        corrected = ctx.keyword.model_copy(update={"args": corrected_args})
        attempt = Attempt(
            action=HealAction(
                type=ActionType.RELOCATE,
                description=f"rerun with corrected expectation {actual!r} (was {expected!r})",
                params={"old_expected": expected, "new_expected": actual},
            ),
            succeeded=False,
        )
        try:
            return_value = await asyncio.to_thread(session.rerun_keyword, corrected)
        except (RerunNotSupported, Exception) as exc:  # noqa: B902
            attempt.detail = f"{type(exc).__name__}: {exc}"[:300]
            return HealOutcome(
                status=OutcomeStatus.UNHEALED, diagnosis=diagnosis, attempts=[attempt],
                detail="Rerun with the corrected expectation still failed.",
            )
        attempt.succeeded = True
        return HealOutcome(
            status=OutcomeStatus.HEALED,
            diagnosis=diagnosis,
            attempts=[attempt],
            healed_locator=None,
            return_value_repr=repr(return_value) if return_value is not None else None,
            detail=(
                f"Assertion drift healed: expected value updated from {expected!r} to {actual!r} "
                "for this run. Update the test expectation permanently."
            ),
        )
