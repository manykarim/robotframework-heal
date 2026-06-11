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
    "- Frames/iframes are containers, NEVER targets. When the intended element appears "
    "inside a section marked `<!-- FRAME <chain> ... -->`, prefix your selector with "
    "that chain, e.g. `id=content-frame >>> css=#submit`.\n"
    "- Every proposal must match EXACTLY ONE element in the provided DOM."
)


@dataclass
class LocatorDeps:
    """Per-transaction verification state (the agent itself is cached/shared)."""

    driver: object  # SessionDriver (duck-typed; main-thread-proxied under RF)
    keyword_name: str = ""
    keyword_args: list[str] = field(default_factory=list)
    verified: list[str] = field(default_factory=list)
    rejected: dict[str, str] = field(default_factory=dict)

    def expected_option_values(self) -> list[str]:
        """For select keywords: the option texts/values the keyword will pick.

        `Select Options By    locator    text|label|value    v1    v2 ...`
        (index-based selection can't be text-checked).
        """
        if "select options" not in self.keyword_name.lower() or len(self.keyword_args) < 3:
            return []
        if self.keyword_args[1].lower() in ("text", "label", "value"):
            return [v for v in self.keyword_args[2:] if v]
        return []


#: container/document elements are NEVER valid interaction targets — clicking
#: an iframe "succeeds" without doing what the test meant (proven false heal,
#: experiments/dom-edge-cases/FINDINGS.md)
BLOCKED_TARGET_TAGS = frozenset({"iframe", "frame", "html", "body", "head"})

#: keyword-name marker -> tag names the target element must have
_KEYWORD_TAGS: tuple[tuple[tuple[str, ...], frozenset[str]], ...] = (
    (("select options", "deselect options"), frozenset({"select"})),
    (("fill", "type text", "type secret", "press keys", "clear text"), frozenset({"input", "textarea"})),
    (("check checkbox", "uncheck checkbox"), frozenset({"input"})),
)


def required_tags(keyword_name: str) -> frozenset[str] | None:
    lowered = keyword_name.lower()
    for markers, tags in _KEYWORD_TAGS:
        if any(marker in lowered for marker in markers):
            return tags
    return None


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
                # driver-specific refinement (e.g. ':visible >> nth=0' on Browser)
                refiner = getattr(deps.driver, "disambiguate", None)
                refined = await asyncio.to_thread(refiner, locator) if refiner else None
                if refined:
                    verified.append(refined)
                    continue
                deps.rejected[locator] = f"matched {count} elements, need exactly 1"
                verdicts.append(
                    f"{locator!r}: matched {count} elements, need exactly 1 — add nth-of-type, "
                    "an ancestor with an id, or text refinement"
                )
                continue
            visible = await asyncio.to_thread(deps.driver.is_visible, locator)
            if not visible:
                deps.rejected[locator] = "matches a hidden element"
                verdicts.append(f"{locator!r}: matches a hidden element")
                continue
            info_fn = getattr(deps.driver, "get_element_info", None)
            if info_fn is None:
                verified.append(locator)
                continue
            info = await asyncio.to_thread(info_fn, locator)
            tag = (info.tag_name or "").lower()
            if tag in BLOCKED_TARGET_TAGS:
                reason = (
                    f"resolves to a <{tag}> — frames and document containers are never "
                    "interaction targets; propose the element INSIDE it instead"
                )
                deps.rejected[locator] = reason
                verdicts.append(f"{locator!r}: {reason}")
                continue
            tags = required_tags(deps.keyword_name)
            if tags is not None:
                if tag and tag not in tags:
                    reason = (
                        f"matches a <{tag}>, but {deps.keyword_name!r} needs "
                        f"{' or '.join(sorted(f'<{t}>' for t in tags))}"
                    )
                    deps.rejected[locator] = reason
                    verdicts.append(f"{locator!r}: {reason}")
                    continue
                # argument-aware: a <select> must contain the wanted options
                # (its innerText is the concatenation of option labels)
                wanted = deps.expected_option_values()
                if tag == "select" and wanted and info.inner_text:
                    missing = [v for v in wanted if v not in info.inner_text]
                    if missing:
                        reason = (
                            f"is a <select> but does not contain option(s) {missing} — "
                            "find the select whose options include them"
                        )
                        deps.rejected[locator] = reason
                        verdicts.append(f"{locator!r}: {reason}")
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
