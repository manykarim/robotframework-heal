"""Locator-drift failure class: the locator matches nothing on the live page.

Detection is deterministic (count == 0). Healing: locator agent proposes,
the agent's output validator verifies every candidate against the live
session, the engine reruns the keyword with the best verified locator.
"""

from __future__ import annotations

import asyncio

from ..agents.locator import LocatorDeps, build_user_prompt, get_locator_agent
from ..schemas import (
    ActionType,
    Attempt,
    Confidence,
    Diagnosis,
    EvidenceKind,
    FailureClass,
    FailureContext,
    FixProposal,
    HealAction,
    HealOutcome,
    OutcomeStatus,
)
from ..session import HealSession, RerunNotSupported
from .base import FailureClassPlugin


class LocatorDriftPlugin(FailureClassPlugin):
    failure_class = FailureClass.LOCATOR_DRIFT
    heal_evidence = (EvidenceKind.DOM_EXCERPT,)

    def detect(self, ctx: FailureContext, session: HealSession) -> Diagnosis | None:
        if not ctx.failed_locator or session.driver is None:
            return None
        count = session.driver.count(ctx.failed_locator)
        if count == 0:
            return Diagnosis(
                failure_class=FailureClass.LOCATOR_DRIFT,
                confidence=Confidence.HIGH,
                rationale=f"Locator {ctx.failed_locator!r} matches 0 elements on the live page.",
            )
        if count > 1 and ("strict mode" in ctx.error_message or "waiting for" in ctx.error_message):
            return Diagnosis(
                failure_class=FailureClass.LOCATOR_DRIFT,
                confidence=Confidence.MEDIUM,
                rationale=f"Locator {ctx.failed_locator!r} is ambiguous: it matches {count} elements.",
            )
        return None

    async def heal(self, ctx, session, runtime, budget, diagnosis) -> HealOutcome:
        agent = get_locator_agent(runtime)
        deps = LocatorDeps(
            driver=session.driver,
            keyword_name=ctx.keyword.name,
            keyword_args=list(ctx.keyword.args),
        )
        attempts: list[Attempt] = []
        try:
            result = await agent.run(
                build_user_prompt(ctx), deps=deps, usage_limits=budget.usage_limits
            )
        except Exception as exc:
            return HealOutcome(
                status=OutcomeStatus.UNHEALED,
                diagnosis=diagnosis,
                attempts=[
                    Attempt(
                        action=HealAction(type=ActionType.RELOCATE, description="locator proposal"),
                        succeeded=False,
                        detail=f"{type(exc).__name__}: {exc}"[:300],
                    )
                ],
                detail="No locator proposal survived live verification."
                + (f" Rejected: {deps.rejected}" if deps.rejected else ""),
            )
        runtime_usage = result.usage

        for locator in result.output.locators:
            attempt = Attempt(
                action=HealAction(
                    type=ActionType.RELOCATE,
                    description=f"rerun with verified locator {locator!r}",
                    params={"locator": locator},
                ),
                succeeded=False,
            )
            try:
                return_value = await asyncio.to_thread(
                    session.rerun_keyword, ctx.keyword, locator_override=locator
                )
            except RerunNotSupported:
                attempt.detail = "surface cannot rerun keywords"
                attempts.append(attempt)
                break
            except Exception as exc:
                attempt.detail = f"{type(exc).__name__}: {exc}"[:300]
                attempts.append(attempt)
                continue
            attempt.succeeded = True
            attempts.append(attempt)
            outcome = HealOutcome(
                status=OutcomeStatus.HEALED,
                diagnosis=diagnosis,
                attempts=attempts,
                healed_locator=locator,
                return_value_repr=repr(return_value) if return_value is not None else None,
                detail=f"Replaced broken locator {ctx.failed_locator!r} with verified {locator!r}.",
            )
            outcome.usage.requests = runtime_usage.requests or 0
            outcome.usage.total_tokens = runtime_usage.total_tokens or 0
            return outcome

        return HealOutcome(
            status=OutcomeStatus.UNHEALED,
            diagnosis=diagnosis,
            attempts=attempts,
            detail="Verified locator proposals existed but the keyword still failed on rerun.",
        )

    def synthesize_fix(self, ctx: FailureContext, outcome: HealOutcome) -> FixProposal | None:
        if outcome.status is not OutcomeStatus.HEALED or not outcome.healed_locator:
            return None
        if not ctx.keyword.source:
            return None
        return FixProposal(
            file=ctx.keyword.source,
            lineno=ctx.keyword.lineno,
            kind="locator",
            target=ctx.keyword.name,
            old_value=ctx.failed_locator or "",
            new_value=outcome.healed_locator,
            rationale=outcome.detail,
            confidence=outcome.diagnosis.confidence,
        )
