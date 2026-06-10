"""Locator agent: propose alternative locators, verified live inside the loop.

Verification happens in the output validator — it works in every output mode
(probe-verified down to 8B prompted-JSON models). Each rejected round feeds
per-candidate results back via ModelRetry so the model corrects itself.
Exploration tools are attached only on probed-reliable backends.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic_ai import Agent, ModelRetry, RunContext

from ..runtime import AgentRuntime
from ..schemas import EvidenceKind, FailureContext, LocatorProposals

ROLE = "locator"

SYSTEM_PROMPT = (
    "You repair broken locators for Robot Framework UI tests.\n"
    "You receive the failed locator, the keyword, the error message and a simplified DOM "
    "of the live page. Propose up to 5 alternative locators for the element the test "
    "intended to target, best candidate first.\n"
    "Rules:\n"
    "- Use CSS selectors prefixed with 'css=' (preferred) or XPath prefixed with 'xpath='.\n"
    "- Prefer stable attributes: id, name, placeholder, role, visible text.\n"
    "- 'Fill Text'/'Type'/'Press Keys' keywords target input or textarea elements.\n"
    "- 'Click'/'Check' keywords target button, a, input, label or li elements.\n"
    "- 'Select Options' keywords target select elements.\n"
    "- Every proposal must match EXACTLY ONE element in the provided DOM."
)


@dataclass
class LocatorDeps:
    """Per-transaction verification state (the agent itself is cached/shared)."""

    driver: object  # SessionDriver (duck-typed; main-thread-proxied under RF)
    keyword_name: str = ""
    verified: list[str] = field(default_factory=list)
    rejected: dict[str, str] = field(default_factory=dict)


def _configure(agent: Agent) -> None:
    @agent.output_validator
    async def verify_live(ctx: RunContext[LocatorDeps], output: LocatorProposals) -> LocatorProposals:
        import asyncio

        deps = ctx.deps
        verdicts: list[str] = []
        verified: list[str] = []
        viewport_limited = bool(getattr(deps.driver, "dom_covers_viewport_only", False))
        for locator in output.locators[:8]:
            locator = locator.strip()
            if not locator or locator in deps.rejected:
                continue
            count = await asyncio.to_thread(deps.driver.count, locator)
            if count == 0 and viewport_limited:
                # mobile: candidate may be off-screen — swipe search before rejecting
                if await asyncio.to_thread(deps.driver.scroll_into_view, locator):
                    count = await asyncio.to_thread(deps.driver.count, locator)
            if count == 0:
                deps.rejected[locator] = "matched 0 elements"
                verdicts.append(f"{locator!r}: matched 0 elements")
                continue
            if count > 1:
                deps.rejected[locator] = f"matched {count} elements, need exactly 1"
                verdicts.append(f"{locator!r}: matched {count} elements, need exactly 1")
                continue
            visible = await asyncio.to_thread(deps.driver.is_visible, locator)
            if not visible:
                deps.rejected[locator] = "matches a hidden element"
                verdicts.append(f"{locator!r}: matches a hidden element")
                continue
            verified.append(locator)
        if not verified:
            raise ModelRetry(
                "None of the proposed locators passed live verification:\n"
                + "\n".join(verdicts or ["no usable proposals"])
                + "\nPropose different locators using attributes visible in the DOM."
            )
        deps.verified = verified
        return LocatorProposals(locators=verified, rationale=output.rationale)


def get_locator_agent(runtime: AgentRuntime) -> Agent:
    return runtime.build_agent(
        ROLE,
        LocatorProposals,
        system_prompt=SYSTEM_PROMPT,
        deps_type=LocatorDeps,
        configure=_configure,
    )


def build_user_prompt(ctx: FailureContext) -> str:
    parts = [
        f"failed_locator: {ctx.failed_locator}",
        f"keyword: {ctx.keyword.name}",
        f"arguments: {ctx.keyword.args}",
        f"error_message: {ctx.error_message}",
    ]
    dom = ctx.evidence_of(EvidenceKind.DOM_EXCERPT)
    if dom and dom.excerpt:
        parts.append(f"page_source:\n```html\n{dom.excerpt}\n```")
    parts.append("Propose verified replacement locators for the intended element.")
    return "\n".join(parts)
