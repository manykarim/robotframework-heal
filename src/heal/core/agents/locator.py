"""Locator agents: tiered selection (default) and generation fallback.

Both modes share one live-verification routine running inside output
validators (works in every output mode, down to prompted-JSON 8B models):
exists, unique (with driver disambiguation), visible, not a blocked
container, type-compatible with the keyword, select-option content.

Selection mode (experiments/selection-mode/FINDINGS.md): deterministic
candidates + element info, model returns an index — −68% prompt size and
higher accuracy on every tested model (+27pts on llama-3.1-8B). Fuzzy
ranking ORDERS candidates but never decides: 1/53 recorded cases produced a
plausible-but-wrong confident match that live verification cannot catch.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field

from pydantic import BaseModel
from pydantic_ai import Agent, ModelRetry, RunContext

from ..runtime import AgentRuntime
from ..schemas import EvidenceKind, FailureContext, LocatorProposals

GENERATION_ROLE = "locator"
SELECTION_ROLE = "locator"  # same backend role; different agent/schema
SELECTION_TOP_K = 8

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

GENERATION_SYSTEM_PROMPT = (
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

SELECTION_SYSTEM_PROMPT = (
    "You repair broken locators for Robot Framework UI tests by choosing among "
    "verified candidate elements.\n"
    "You receive the failed locator, the keyword, and a ranked candidate list with "
    "each element's tag, text and attributes. Pick the candidate that matches the "
    "test's INTENT (what the failed locator and keyword were trying to do).\n"
    "Respond with the candidate's index."
)


def required_tags(keyword_name: str) -> frozenset[str] | None:
    lowered = keyword_name.lower()
    for markers, tags in _KEYWORD_TAGS:
        if any(marker in lowered for marker in markers):
            return tags
    return None


@dataclass
class LocatorDeps:
    """Per-transaction verification state (agents are cached/shared)."""

    driver: object  # SessionDriver (duck-typed; main-thread-proxied under RF)
    keyword_name: str = ""
    keyword_args: list[str] = field(default_factory=list)
    #: selection mode: index -> candidate locator
    candidates: dict[int, str] = field(default_factory=dict)
    verified: list[str] = field(default_factory=list)
    rejected: dict[str, str] = field(default_factory=dict)

    def expected_option_values(self) -> list[str]:
        """For select keywords: the option texts/values the keyword will pick."""
        if "select options" not in self.keyword_name.lower() or len(self.keyword_args) < 3:
            return []
        if self.keyword_args[1].lower() in ("text", "label", "value"):
            return [v for v in self.keyword_args[2:] if v]
        return []


async def verify_candidate(deps: LocatorDeps, locator: str) -> str | None:
    """Live verification shared by both modes. Returns a rejection reason or None.

    On acceptance the (possibly disambiguated) locator is appended to
    deps.verified; the returned None means 'use deps.verified[-1]'.
    """
    driver = deps.driver
    count = await asyncio.to_thread(driver.count, locator)
    viewport_limited = bool(getattr(driver, "dom_covers_viewport_only", False))
    if count == 0 and viewport_limited:
        if await asyncio.to_thread(driver.scroll_into_view, locator):
            count = await asyncio.to_thread(driver.count, locator)
    if count == 0:
        return "matched 0 elements"
    if count > 1:
        refiner = getattr(driver, "disambiguate", None)
        refined = await asyncio.to_thread(refiner, locator) if refiner else None
        if refined:
            locator = refined
        else:
            return (
                f"matched {count} elements, need exactly 1 — add nth-of-type, "
                "an ancestor with an id, or text refinement"
            )
    if not await asyncio.to_thread(driver.is_visible, locator):
        return "matches a hidden element"
    info_fn = getattr(driver, "get_element_info", None)
    if info_fn is not None:
        info = await asyncio.to_thread(info_fn, locator)
        tag = (info.tag_name or "").lower()
        if tag in BLOCKED_TARGET_TAGS:
            return (
                f"resolves to a <{tag}> — frames and document containers are never "
                "interaction targets; propose the element INSIDE it instead"
            )
        tags = required_tags(deps.keyword_name)
        if tags is not None:
            if tag and tag not in tags:
                return (
                    f"matches a <{tag}>, but {deps.keyword_name!r} needs "
                    f"{' or '.join(sorted(f'<{t}>' for t in tags))}"
                )
            wanted = deps.expected_option_values()
            if tag == "select" and wanted and info.inner_text:
                missing = [v for v in wanted if v not in info.inner_text]
                if missing:
                    return (
                        f"is a <select> but does not contain option(s) {missing} — "
                        "find the select whose options include them"
                    )
    deps.verified.append(locator)
    return None


# ----------------------------------------------------------- generation mode


def _configure_generation(agent: Agent) -> None:
    @agent.output_validator
    async def verify_live(ctx: RunContext[LocatorDeps], output: LocatorProposals) -> LocatorProposals:
        deps = ctx.deps
        verdicts: list[str] = []
        accepted: list[str] = []
        for locator in output.locators[:8]:
            locator = locator.strip()
            if not locator or locator in deps.rejected:
                continue
            reason = await verify_candidate(deps, locator)
            if reason is None:
                accepted.append(deps.verified[-1])
            else:
                deps.rejected[locator] = reason
                verdicts.append(f"{locator!r}: {reason}")
        if not accepted:
            raise ModelRetry(
                "None of the proposed locators passed live verification:\n"
                + "\n".join(verdicts or ["no usable proposals"])
                + "\nPropose different locators using attributes visible in the DOM."
            )
        return LocatorProposals(locators=accepted, rationale=output.rationale)


def get_locator_agent(runtime: AgentRuntime) -> Agent:
    return runtime.build_agent(
        GENERATION_ROLE,
        LocatorProposals,
        system_prompt=GENERATION_SYSTEM_PROMPT,
        deps_type=LocatorDeps,
        configure=_configure_generation,
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


# ------------------------------------------------------------ selection mode


class SelectionPick(BaseModel):
    """Flat on purpose — emittable by prompted-JSON-only small models."""

    index: int
    reason: str = ""


def _configure_selection(agent: Agent) -> None:
    @agent.output_validator
    async def verify_pick(ctx: RunContext[LocatorDeps], output: SelectionPick) -> SelectionPick:
        deps = ctx.deps
        locator = deps.candidates.get(output.index)
        if locator is None:
            raise ModelRetry(
                f"index {output.index} is not in the candidate list; pick one of "
                f"{sorted(deps.candidates)}"
            )
        reason = await verify_candidate(deps, locator)
        if reason is not None:
            deps.rejected[locator] = reason
            remaining = {i: loc for i, loc in deps.candidates.items() if loc not in deps.rejected}
            raise ModelRetry(
                f"candidate {output.index} ({locator!r}) failed live verification: {reason}. "
                f"Pick a different index from {sorted(remaining) or 'NONE LEFT'}."
            )
        return output


def get_selection_agent(runtime: AgentRuntime) -> Agent:
    return runtime.build_agent(
        SELECTION_ROLE,
        SelectionPick,
        system_prompt=SELECTION_SYSTEM_PROMPT,
        deps_type=LocatorDeps,
        configure=_configure_selection,
    )


def build_selection_prompt(ctx: FailureContext, ranked_candidates: list[dict]) -> str:
    slim = [
        {k: v for k, v in info.items() if k in ("index", "locator", "tag", "text", "attrs")}
        for info in ranked_candidates
    ]
    return "\n".join(
        [
            f"failed_locator: {ctx.failed_locator}",
            f"keyword: {ctx.keyword.name}",
            f"arguments: {ctx.keyword.args}",
            "Pick the candidate that matches the test's intent. Respond with its index.",
            f"candidates:\n{json.dumps(slim)}",
        ]
    )
