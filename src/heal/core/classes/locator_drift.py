"""Locator-drift failure class: the locator matches nothing on the live page
(or is ambiguous). Healing is a tiered ladder (design D3):

  1. deterministic candidates from the DOM, fuzzy-RANKED (never deciding)
  2. selection agent picks an index from the top-K (validator live-verifies)
  3. generation agent with the full DOM as fallback

Both agent modes share the same live verification; the engine reruns the
keyword with the verified locator.
"""

from __future__ import annotations

import asyncio

from ..agents.locator import (
    SELECTION_TOP_K,
    LocatorDeps,
    build_selection_prompt,
    build_user_prompt,
    get_locator_agent,
    get_selection_agent,
)
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
        attempts: list[Attempt] = []
        if runtime.settings.locator_tiers == "selection":
            outcome = await self._heal_by_selection(ctx, session, runtime, budget, diagnosis, attempts)
            if outcome is not None:
                return outcome
            # selection had nothing / exhausted -> fall through to generation
        return await self._heal_by_generation(ctx, session, runtime, budget, diagnosis, attempts)

    async def _heal_by_selection(
        self, ctx, session, runtime, budget, diagnosis, attempts: list[Attempt]
    ) -> HealOutcome | None:
        """Tiers 1+2: rank deterministic candidates, agent picks an index.

        Returns None to signal fallthrough to generation mode.
        """
        from ...drivers.dom import candidate_tags_for, describe_candidates, generate_proposals, rank_candidates

        dom_evidence = ctx.evidence_of(EvidenceKind.DOM_EXCERPT)
        if dom_evidence is None or not dom_evidence.excerpt:
            return None
        # frame sections carry pierce prefixes bs4 selectors can't express;
        # frame-content healing is generation mode's job
        main_dom = dom_evidence.excerpt.split("<!-- FRAME ")[0]
        try:
            candidates = await asyncio.to_thread(
                generate_proposals, main_dom, candidate_tags_for(ctx.keyword.name)
            )
            infos = describe_candidates(main_dom, candidates)
            ranked = rank_candidates(infos, ctx.failed_locator or "")[:SELECTION_TOP_K]
        except Exception:
            return None
        if not ranked:
            attempts.append(
                Attempt(
                    action=HealAction(type=ActionType.RELOCATE, description="candidate generation (tier 1)"),
                    succeeded=False,
                    detail="no deterministic candidates",
                )
            )
            return None
        deps = LocatorDeps(
            driver=session.driver,
            keyword_name=ctx.keyword.name,
            keyword_args=list(ctx.keyword.args),
            candidates={info["index"]: info["locator"] for info in ranked},
        )
        try:
            result = await get_selection_agent(runtime).run(
                build_selection_prompt(ctx, ranked), deps=deps, usage_limits=budget.usage_limits
            )
        except Exception as exc:
            attempts.append(
                Attempt(
                    action=HealAction(type=ActionType.RELOCATE, description="candidate selection (tier 2)"),
                    succeeded=False,
                    detail=f"{type(exc).__name__}: {exc}"[:200]
                    + (f" rejected: {deps.rejected}" if deps.rejected else ""),
                )
            )
            return None
        verified = deps.verified[-1] if deps.verified else deps.candidates[result.output.index]
        outcome = await self._rerun_with(ctx, session, diagnosis, [verified], attempts)
        # record token usage regardless of outcome (cost of a failed heal is real)
        outcome.usage.requests = result.usage.requests or 0
        outcome.usage.total_tokens = result.usage.total_tokens or 0
        if outcome.status is OutcomeStatus.HEALED:
            return outcome
        return None  # selected element didn't survive rerun -> generation fallback

    async def _heal_by_generation(
        self, ctx, session, runtime, budget, diagnosis, attempts: list[Attempt]
    ) -> HealOutcome:
        agent = get_locator_agent(runtime)
        deps = LocatorDeps(
            driver=session.driver,
            keyword_name=ctx.keyword.name,
            keyword_args=list(ctx.keyword.args),
        )
        try:
            result = await agent.run(
                build_user_prompt(ctx), deps=deps, usage_limits=budget.usage_limits
            )
        except Exception as exc:
            return HealOutcome(
                status=OutcomeStatus.UNHEALED,
                diagnosis=diagnosis,
                attempts=attempts
                + [
                    Attempt(
                        action=HealAction(type=ActionType.RELOCATE, description="locator proposal"),
                        succeeded=False,
                        detail=f"{type(exc).__name__}: {exc}"[:300],
                    )
                ],
                detail="No locator proposal survived live verification."
                + (f" Rejected: {deps.rejected}" if deps.rejected else ""),
            )
        outcome = await self._rerun_with(ctx, session, diagnosis, result.output.locators, attempts)
        # record token usage regardless of outcome (cost of a failed heal is real)
        outcome.usage.requests = result.usage.requests or 0
        outcome.usage.total_tokens = result.usage.total_tokens or 0
        return outcome

    async def _rerun_with(
        self, ctx, session, diagnosis, locators: list[str], attempts: list[Attempt]
    ) -> HealOutcome:
        for locator in locators:
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
            return HealOutcome(
                status=OutcomeStatus.HEALED,
                diagnosis=diagnosis,
                attempts=attempts,
                healed_locator=locator,
                return_value_repr=repr(return_value) if return_value is not None else None,
                detail=f"Replaced broken locator {ctx.failed_locator!r} with verified {locator!r}.",
            )

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
