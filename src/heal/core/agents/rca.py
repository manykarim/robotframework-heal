"""RCA agent: turns a finished transaction into a clean root-cause narrative.

Invoked for UNHEALED transactions (healed ones get good template messages for
free). Failures degrade to the engine's template RCA — never to a crash.
"""

from __future__ import annotations

from pydantic import BaseModel
from pydantic_ai.usage import UsageLimits

from ..runtime import AgentRuntime
from ..schemas import EvidenceKind, FailureContext, HealOutcome

ROLE = "rca"

SYSTEM_PROMPT = (
    "You write root-cause analyses for failed Robot Framework UI-test keywords.\n"
    "You receive the failure data, evidence excerpts, healing attempts that were tried, "
    "and version-control context for the test file.\n"
    "Write for the test maintainer: state what the keyword tried to do, what the page "
    "actually contained, the most likely root cause (distinguish 'test outdated' from "
    "'application changed' from 'application defect'), and the concrete permanent fix.\n"
    "Never include stack traces. Be specific and brief."
)


class RcaDraft(BaseModel):
    clean_message: str
    root_cause: str = ""
    suggested_fix: str = ""


def build_user_prompt(ctx: FailureContext, outcome: HealOutcome) -> str:
    parts = [
        f"test: {ctx.test_name} (suite {ctx.suite_name})",
        f"keyword: {ctx.keyword.name}  arguments: {ctx.keyword.args}",
        f"error_message: {ctx.error_message}",
        f"diagnosed_failure_class: {outcome.diagnosis.failure_class.value} ({outcome.diagnosis.rationale})",
    ]
    if outcome.attempts:
        tried = "; ".join(
            f"{a.action.description} -> {'ok' if a.succeeded else (a.detail or 'failed')}"
            for a in outcome.attempts
        )
        parts.append(f"healing_attempts: {tried}")
    for kind in (EvidenceKind.GIT_HISTORY, EvidenceKind.SOURCE_EXCERPT, EvidenceKind.DOM_EXCERPT):
        evidence = ctx.evidence_of(kind)
        if evidence and evidence.excerpt:
            parts.append(f"{kind.value}:\n```\n{evidence.excerpt[:4000]}\n```")
    parts.append("Write the root-cause analysis.")
    return "\n".join(parts)


async def run_rca(
    runtime: AgentRuntime,
    ctx: FailureContext,
    outcome: HealOutcome,
    usage_limits: UsageLimits | None = None,
) -> RcaDraft | None:
    agent = runtime.build_agent(ROLE, RcaDraft, system_prompt=SYSTEM_PROMPT)
    try:
        result = await agent.run(build_user_prompt(ctx, outcome), usage_limits=usage_limits)
    except Exception:
        return None
    return result.output
