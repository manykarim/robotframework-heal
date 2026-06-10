"""Triage agent: single-shot failure classification when detectors are silent.

Flat Diagnosis schema, curated evidence excerpts, no tools — works on every
model tier down to prompted-JSON-only backends.
"""

from __future__ import annotations

from pydantic_ai.usage import UsageLimits

from ..runtime import AgentRuntime
from ..schemas import Confidence, Diagnosis, EvidenceKind, FailureClass, FailureContext

ROLE = "triage"

SYSTEM_PROMPT = (
    "You classify Robot Framework UI-test failures.\n"
    "failure_class must be one of: locator-drift (element not found / selector matches nothing), "
    "timing (page or data still loading), viewport (element exists but is not scrolled into view), "
    "overlay (a dialog/banner blocks the interaction), form-state (submit blocked by required or "
    "invalid form fields), assertion-drift (expected value differs from actual UI text), "
    "unknown (none of the above clearly applies).\n"
    "confidence must be one of: low, medium, high.\n"
    "Base your judgment ONLY on the provided failure data and evidence."
)

_PROMPT_EVIDENCE = (EvidenceKind.DOM_EXCERPT, EvidenceKind.SOURCE_EXCERPT)


def build_user_prompt(ctx: FailureContext) -> str:
    parts = [
        f"keyword: {ctx.keyword.name}",
        f"arguments: {ctx.keyword.args}",
        f"library: {ctx.keyword.owner_library}",
        f"error_message: {ctx.error_message}",
    ]
    if ctx.failed_locator:
        parts.append(f"failed_locator: {ctx.failed_locator}")
    for kind in _PROMPT_EVIDENCE:
        evidence = ctx.evidence_of(kind)
        if evidence and evidence.excerpt:
            parts.append(f"{kind.value}:\n```\n{evidence.excerpt}\n```")
    parts.append("Classify this failure.")
    return "\n".join(parts)


async def run_triage(
    runtime: AgentRuntime, ctx: FailureContext, usage_limits: UsageLimits | None = None
):
    """Classify; returns (Diagnosis, usage). Falls back to UNKNOWN on agent failure."""
    agent = runtime.build_agent(ROLE, Diagnosis, system_prompt=SYSTEM_PROMPT)
    try:
        result = await agent.run(build_user_prompt(ctx), usage_limits=usage_limits)
    except Exception as exc:  # agent/transport failure must never kill the pipeline
        return (
            Diagnosis(
                failure_class=FailureClass.UNKNOWN,
                confidence=Confidence.LOW,
                rationale=f"Triage agent unavailable: {type(exc).__name__}: {exc}"[:300],
            ),
            None,
        )
    return result.output, result.usage()
