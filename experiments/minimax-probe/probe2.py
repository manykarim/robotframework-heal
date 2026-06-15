"""Probe 2: why does tool-based output fail on MiniMax when raw tool calling works?

Hypotheses:
  H1 strict tool definitions (strict: true) break MiniMax tool calls
  H2 forced tool_choice (required / named function) breaks MiniMax tool calls
Tests run the P1 triage task under profile variants, then re-run P4 (tool loop)
and P6 (healing proposals) under the winning profile.
"""

import asyncio
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.profiles.openai import OpenAIModelProfile
from pydantic_ai.providers.openai import OpenAIProvider

load_dotenv(Path(__file__).parents[2] / ".env")

MODEL_NAME = os.environ.get("PROBE_MODEL", "MiniMax-M2.5")


def make_model(strict: bool, tool_choice_required: bool) -> OpenAIChatModel:
    return OpenAIChatModel(
        MODEL_NAME,
        provider=OpenAIProvider(
            base_url="https://api.minimax.io/v1",
            api_key=os.environ["MINIMAX_API_KEY"],
        ),
        profile=OpenAIModelProfile(
            openai_supports_strict_tool_definition=strict,
            openai_supports_tool_choice_required=tool_choice_required,
        ),
    )


class Diagnosis(BaseModel):
    failure_class: str
    confidence: str
    rationale: str


PAGE = """<html><body><form id="login-form">
<label for="user-email">Email</label><input id="user-email" type="text"/>
<button id="signin-btn" type="submit">Sign in</button></form></body></html>"""

TRIAGE_PROMPT = (
    "A Robot Framework keyword failed.\n"
    "keyword: Click  args: ['id=login-button']\n"
    "error: TimeoutError waiting for locator('id=login-button')\n"
    f"page excerpt: {PAGE}\n"
    "Classify: failure_class in [locator-drift, timing, viewport, overlay, form-state, assertion-drift, unknown]; "
    "confidence in [low, medium, high]."
)

results = []


async def triage_variant(name: str, strict: bool, tcr: bool):
    t0 = time.time()
    try:
        agent = Agent(make_model(strict, tcr), output_type=Diagnosis)
        res = await agent.run(TRIAGE_PROMPT)
        ok = res.output.failure_class == "locator-drift"
        results.append((name, ok, time.time() - t0, f"{res.output.failure_class}"))
    except Exception as e:
        results.append((name, False, time.time() - t0, f"{type(e).__name__}: {e}"[:160]))
    print(f"{name}: {results[-1]}")


async def tool_loop(name: str, strict: bool, tcr: bool):
    t0 = time.time()
    calls = []
    agent = Agent(
        make_model(strict, tcr),
        output_type=Diagnosis,
        system_prompt="Diagnose RF failures. ALWAYS call query_dom before answering.",
    )

    @agent.tool
    async def query_dom(ctx: RunContext[None], css_selector: str) -> str:
        """Return match count and HTML for a CSS selector."""
        calls.append(css_selector)
        if "button" in css_selector or "signin" in css_selector or "submit" in css_selector:
            return '1 match: <button id="signin-btn" type="submit">Sign in</button>'
        return "0 matches"

    try:
        res = await agent.run(
            "Click on 'id=login-button' failed: locator not found (login form page). "
            "Diagnose failure_class/confidence."
        )
        ok = len(calls) > 0 and res.output.failure_class == "locator-drift"
        results.append((name, ok, time.time() - t0, f"tool called {len(calls)}x {calls[:2]}"))
    except Exception as e:
        results.append((name, False, time.time() - t0, f"{type(e).__name__}: {e}"[:160]))
    print(f"{name}: {results[-1]}")


async def healing(name: str, strict: bool, tcr: bool):
    t0 = time.time()

    class LocatorProposals(BaseModel):
        locators: list[str]

    try:
        agent = Agent(make_model(strict, tcr), output_type=LocatorProposals)
        res = await agent.run(
            "Fix this broken Browser locator.\nfailed_locator: id=login-button\nkeyword: Click\n"
            f"page_source: {PAGE}\nPropose up to 3 CSS locators, best first, prefixed 'css='."
        )
        good = [l for l in res.output.locators if "signin-btn" in l]
        results.append((name, bool(good), time.time() - t0, f"{len(res.output.locators)} proposals, valid: {good[:1]}"))
    except Exception as e:
        results.append((name, False, time.time() - t0, f"{type(e).__name__}: {e}"[:160]))
    print(f"{name}: {results[-1]}")


async def main():
    print(f"=== probe2, model={MODEL_NAME} ===")
    await triage_variant("T-baseline (strict=T, tcr=T)", True, True)
    await triage_variant("T-H1 (strict=F, tcr=T)", False, True)
    await triage_variant("T-H2 (strict=T, tcr=F)", True, False)
    await triage_variant("T-H1+H2 (strict=F, tcr=F)", False, False)
    # winning variant assumed H1+H2; verify tool loop + healing under it
    await tool_loop("P4-retest (strict=F, tcr=F)", False, False)
    await healing("P6-retest (strict=F, tcr=F)", False, False)
    print("\n=== SUMMARY ===")
    for name, ok, dt, note in results:
        print(f"{'PASS' if ok else 'FAIL':4} {dt:6.1f}s  {name:32} {note}")


if __name__ == "__main__":
    asyncio.run(main())
