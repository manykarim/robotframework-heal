"""Failure-class plugin contract and registry.

Each failure class contributes:
* `detect`   — deterministic, cheap, NO LLM; returns a Diagnosis or None
* `heal`     — async remedy attempt (may use agents via the runtime)
* `synthesize_fix` — optional permanent-fix proposal from a healed outcome

Plugins are evaluated in registration order; adding a class never requires
touching the engine.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..schemas import Diagnosis, EvidenceKind, FailureClass, FailureContext, FixProposal, HealOutcome, OutcomeStatus
from ..session import HealSession

if TYPE_CHECKING:
    from ..ledger import TransactionBudget
    from ..runtime import AgentRuntime


class FailureClassPlugin:
    """Base class with safe defaults: detect-nothing, heal-nothing."""

    #: FailureClass this plugin owns.
    failure_class: FailureClass = FailureClass.UNKNOWN
    #: Evidence kinds `detect` needs (collected before detect is called).
    detect_evidence: tuple[EvidenceKind, ...] = ()
    #: Additional evidence kinds `heal` needs.
    heal_evidence: tuple[EvidenceKind, ...] = ()

    def detect(self, ctx: FailureContext, session: HealSession) -> Diagnosis | None:
        return None

    async def heal(
        self,
        ctx: FailureContext,
        session: HealSession,
        runtime: "AgentRuntime",
        budget: "TransactionBudget",
        diagnosis: Diagnosis,
    ) -> HealOutcome:
        return HealOutcome(
            status=OutcomeStatus.UNHEALED,
            diagnosis=diagnosis,
            detail=f"No healing strategy implemented for {self.failure_class.value}.",
        )

    def synthesize_fix(self, ctx: FailureContext, outcome: HealOutcome) -> FixProposal | None:
        return None


class PluginRegistry:
    def __init__(self, plugins: list[FailureClassPlugin] | None = None):
        self._plugins: list[FailureClassPlugin] = list(plugins or [])

    def register(self, plugin: FailureClassPlugin) -> None:
        self._plugins.append(plugin)

    def __iter__(self):
        return iter(self._plugins)

    def for_class(self, failure_class: FailureClass) -> FailureClassPlugin | None:
        return next((p for p in self._plugins if p.failure_class is failure_class), None)
