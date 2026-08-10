"""The healing engine: one explicit pipeline per failure, orchestrated in code.

    collect -> detect -> (triage) -> heal -> verify -> rca -> event

Agents are leaf workers invoked by plugins/stages; the engine owns ordering,
budgets, suppression and bookkeeping. No LLM ever decides routing.
"""

from __future__ import annotations

import asyncio
import itertools
import time

from .agents.rca import run_rca
from .agents.triage import run_triage
from .classes.assertion_drift import AssertionDriftPlugin
from .classes.base import FailureClassPlugin, PluginRegistry
from .classes.form_state import FormStatePlugin
from .classes.locator_drift import LocatorDriftPlugin
from .classes.overlay import OverlayPlugin
from .classes.timing import TimingPlugin
from .classes.viewport import ViewportPlugin
from .evidence import ContextBuilder
from .ledger import RunLedger
from .runtime import AgentRuntime
from .schemas import (
    Confidence,
    Diagnosis,
    EvidenceKind,
    FailureClass,
    HealEvent,
    HealOutcome,
    OutcomeStatus,
    RcaRecord,
)
from .session import HealSession


def default_registry() -> PluginRegistry:
    """Detection order is deliberate: a loading page explains everything; a
    blocking dialog beats out-of-viewport (both need the element present);
    viewport's mobile branch (absent element, swipe search) runs before
    locator-drift and falls through to it when swiping finds nothing."""
    return PluginRegistry(
        [
            TimingPlugin(),
            OverlayPlugin(),
            ViewportPlugin(),
            AssertionDriftPlugin(),
            FormStatePlugin(),
            LocatorDriftPlugin(),
        ]
    )


class HealingEngine:
    def __init__(
        self,
        runtime: AgentRuntime,
        ledger: RunLedger | None = None,
        registry: PluginRegistry | None = None,
    ) -> None:
        self.runtime = runtime
        self.ledger = ledger or RunLedger(settings=runtime.settings)
        self.registry = registry or default_registry()
        self._event_counter = itertools.count(1)

    async def handle(self, builder: ContextBuilder, session: HealSession) -> HealEvent:
        """Process one failure end-to-end and return the heal event."""
        started = time.monotonic()
        budget = self.ledger.begin_transaction()

        if self.ledger.run_budget_exhausted():
            outcome = self._suppressed("Run token budget exhausted; healing disabled for the rest of the run.")
        else:
            try:
                # Verify the resolved output mode can actually be produced before
                # spending the budget healing in it. Deliberately outside the
                # wait_for below: a probe is not part of the failure budget, and
                # it is cached per endpoint so only the first transaction pays.
                await self.runtime.ensure_safe_output_mode("locator")
                outcome = await asyncio.wait_for(
                    self._process(builder, session, budget),
                    timeout=budget.remaining_seconds(),
                )
            except asyncio.TimeoutError:
                outcome = HealOutcome(
                    status=OutcomeStatus.UNHEALED,
                    diagnosis=Diagnosis(
                        failure_class=FailureClass.UNKNOWN,
                        confidence=Confidence.LOW,
                        rationale="Healing transaction exceeded the per-failure time budget.",
                    ),
                    detail=f"Aborted after {self.runtime.settings.max_failure_seconds:.0f}s (HEAL_MAX_FAILURE_SECONDS).",
                )
            except ValueError as exc:
                if "No model configured" in str(exc):
                    outcome = self._suppressed(
                        f"Healing skipped: {exc}. Configure it in your .env "
                        "(loaded automatically) or the environment."
                    )
                else:
                    outcome = self._engine_error(exc)
            except Exception as exc:  # engine errors must never fail the test run harder
                outcome = self._engine_error(exc)

        outcome.duration_seconds = time.monotonic() - started
        self.ledger.record_outcome(outcome.status.value)
        if outcome.usage.total_tokens:
            self.ledger.record_token_counts(outcome.usage.total_tokens, outcome.usage.requests)

        ctx = builder.context()
        plugin = self.registry.for_class(outcome.diagnosis.failure_class)
        fix = plugin.synthesize_fix(ctx, outcome) if plugin else None

        rca = self._compose_rca(ctx, outcome)
        rca = await self._enrich_rca(ctx, outcome, rca, budget)

        return HealEvent(
            event_id=f"heal-{next(self._event_counter)}",
            test_name=ctx.test_name,
            suite_name=ctx.suite_name,
            source=ctx.keyword.source,
            lineno=ctx.keyword.lineno,
            keyword=ctx.keyword,
            context=ctx,
            outcome=outcome,
            rca=rca,
            fix_proposal=fix,
        )

    # ------------------------------------------------------------------ stages

    async def _process(self, builder: ContextBuilder, session: HealSession, budget) -> HealOutcome:
        plugin, diagnosis = await self._diagnose(builder, session, budget)

        if plugin is None:
            return HealOutcome(
                status=OutcomeStatus.UNHEALED,
                diagnosis=diagnosis,
                detail="No healing plugin registered for this failure class.",
            )

        ctx = builder.context(*plugin.heal_evidence)
        outcome = await plugin.heal(ctx, session, self.runtime, budget, diagnosis)

        # single-hop fallthrough (e.g. viewport swipe-search exhausted -> locator-drift)
        if outcome.status is OutcomeStatus.UNHEALED and outcome.fallthrough_to is not None:
            next_plugin = self.registry.for_class(outcome.fallthrough_to)
            if next_plugin is not None and next_plugin is not plugin:
                next_diagnosis = Diagnosis(
                    failure_class=outcome.fallthrough_to,
                    confidence=diagnosis.confidence,
                    rationale=f"{diagnosis.rationale} (fallthrough from {plugin.failure_class.value})",
                )
                ctx = builder.context(*next_plugin.heal_evidence)
                next_outcome = await next_plugin.heal(ctx, session, self.runtime, budget, next_diagnosis)
                next_outcome.attempts = outcome.attempts + next_outcome.attempts
                return next_outcome
        return outcome

    async def _diagnose(
        self, builder: ContextBuilder, session: HealSession, budget
    ) -> tuple[FailureClassPlugin | None, Diagnosis]:
        # Tier 1: deterministic detectors, in registry order, no LLM.
        for plugin in self.registry:
            ctx = builder.context(*plugin.detect_evidence)
            diagnosis = await asyncio.to_thread(plugin.detect, ctx, session)
            if diagnosis is not None:
                return plugin, diagnosis

        # Tier 2: single-shot triage agent on curated evidence.
        ctx = builder.context(EvidenceKind.DOM_EXCERPT, EvidenceKind.SOURCE_EXCERPT)
        diagnosis, usage = await run_triage(self.runtime, ctx, budget.usage_limits)
        self.ledger.record_usage(usage)
        return self.registry.for_class(diagnosis.failure_class), diagnosis

    # --------------------------------------------------------------------- rca

    def _compose_rca(self, ctx, outcome: HealOutcome) -> RcaRecord:
        """Template-based RCA (the RCA agent of task 6.7 enriches this)."""
        diagnosis = outcome.diagnosis
        if outcome.status is OutcomeStatus.HEALED:
            clean = (
                f"'{ctx.keyword.name}' failed ({diagnosis.failure_class.value}) and was healed: "
                f"{outcome.detail or diagnosis.rationale}"
            )
        elif outcome.status is OutcomeStatus.SUPPRESSED:
            clean = f"'{ctx.keyword.name}' failed; healing was suppressed: {outcome.detail}"
        else:
            clean = (
                f"'{ctx.keyword.name}' failed ({diagnosis.failure_class.value}): "
                f"{diagnosis.rationale or ctx.error_message}"
            )
        git = ctx.evidence_of(EvidenceKind.GIT_HISTORY)
        root_cause = diagnosis.rationale
        if git is not None and git.summary:
            root_cause = f"{root_cause} ({git.summary})" if root_cause else git.summary
        return RcaRecord(
            failure_class=diagnosis.failure_class,
            clean_message=clean,
            root_cause=root_cause,
            suggested_fix=(
                f"Replace the locator with {outcome.healed_locator!r}." if outcome.healed_locator else ""
            ),
            evidence_refs=sorted(ctx.evidence),
            confidence=diagnosis.confidence,
        )

    async def _enrich_rca(self, ctx, outcome: HealOutcome, template: RcaRecord, budget) -> RcaRecord:
        """LLM-enrich the RCA for unhealed failures (template is the fallback)."""
        if outcome.status is not OutcomeStatus.UNHEALED:
            return template
        settings = self.runtime.settings
        if not (settings.rca_model or settings.model):
            return template
        if self.ledger.run_budget_exhausted() or budget.exhausted():
            return template
        try:
            draft = await asyncio.wait_for(
                run_rca(self.runtime, ctx, outcome, budget.usage_limits),
                timeout=max(5.0, budget.remaining_seconds()),
            )
        except Exception:
            return template
        if draft is None:
            return template
        return template.model_copy(
            update={
                "clean_message": draft.clean_message or template.clean_message,
                "root_cause": draft.root_cause or template.root_cause,
                "suggested_fix": draft.suggested_fix or template.suggested_fix,
            }
        )

    @staticmethod
    def _engine_error(exc: Exception) -> HealOutcome:
        return HealOutcome(
            status=OutcomeStatus.UNHEALED,
            diagnosis=Diagnosis(
                failure_class=FailureClass.UNKNOWN,
                confidence=Confidence.LOW,
                rationale=f"Engine error: {type(exc).__name__}: {exc}"[:300],
            ),
        )

    @staticmethod
    def _suppressed(reason: str) -> HealOutcome:
        return HealOutcome(
            status=OutcomeStatus.SUPPRESSED,
            diagnosis=Diagnosis(
                failure_class=FailureClass.UNKNOWN, confidence=Confidence.LOW, rationale=reason
            ),
            detail=reason,
        )
