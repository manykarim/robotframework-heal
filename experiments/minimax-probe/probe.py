"""Probes validating architecture assumptions against MiniMax (OpenAI-compatible endpoint).

Each probe maps to a design assumption:
  P1 ToolOutput        - structured output transported via tool calling
  P2 NativeOutput      - structured output via response_format json_schema
  P3 PromptedOutput    - universal fallback; must survive <think> blocks
  P4 Tool loop         - agent calls an exploration tool, uses its result
  P5 ModelRetry        - output validator bounces bad output, model corrects
  P6 Realistic healing - mini locator-heal task with verification validator
"""

import asyncio
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.output import NativeOutput, PromptedOutput
from pydantic_ai.providers.openai import OpenAIProvider

load_dotenv(Path(__file__).parents[2] / ".env")

MODEL_NAME = os.environ.get("PROBE_MODEL", "MiniMax-M2.5")

model = OpenAIChatModel(
    MODEL_NAME,
    provider=OpenAIProvider(
        base_url="https://api.minimax.io/v1",
        api_key=os.environ["MINIMAX_API_KEY"],
    ),
)


class Diagnosis(BaseModel):
    """Flat schema, austerity rules: no nesting, no unions."""
    failure_class: str
    confidence: str
    rationale: str


PAGE = """<html><body>
<form id="login-form">
  <label for="user-email">Email</label><input id="user-email" name="email" type="text"/>
  <label for="user-pass">Password</label><input id="user-pass" name="password" type="password"/>
  <button id="signin-btn" type="submit">Sign in</button>
</form></body></html>"""

TRIAGE_PROMPT = (
    "A Robot Framework keyword failed.\n"
    "keyword: Click  args: ['id=login-button']\n"
    "error: TimeoutError: locator.click: Timeout 10000ms exceeded waiting for locator('id=login-button')\n"
    f"page excerpt: {PAGE}\n"
    "Classify the failure. failure_class must be one of: "
    "locator-drift, timing, viewport, overlay, form-state, assertion-drift, unknown. "
    "confidence must be one of: low, medium, high."
)

results: list[tuple[str, str, float, str]] = []


def record(probe: str, ok: bool, t0: float, note: str) -> None:
    results.append((probe, "PASS" if ok else "FAIL", time.time() - t0, note))
    print(f"  -> {'PASS' if ok else 'FAIL'} ({time.time() - t0:.1f}s) {note}")


async def p1_tool_output():
    print("P1 ToolOutput (structured output via tool call)")
    t0 = time.time()
    try:
        agent = Agent(model, output_type=Diagnosis)
        res = await agent.run(TRIAGE_PROMPT)
        ok = res.output.failure_class == "locator-drift"
        record("P1 ToolOutput", ok, t0, f"{res.output.failure_class}/{res.output.confidence}, {res.usage().total_tokens} tok")
    except Exception as e:
        record("P1 ToolOutput", False, t0, f"{type(e).__name__}: {e}"[:200])


async def p2_native_output():
    print("P2 NativeOutput (response_format json_schema)")
    t0 = time.time()
    try:
        agent = Agent(model, output_type=NativeOutput(Diagnosis))
        res = await agent.run(TRIAGE_PROMPT)
        ok = res.output.failure_class == "locator-drift"
        record("P2 NativeOutput", ok, t0, f"{res.output.failure_class}/{res.output.confidence}")
    except Exception as e:
        record("P2 NativeOutput", False, t0, f"{type(e).__name__}: {e}"[:200])


async def p3_prompted_output():
    print("P3 PromptedOutput (universal fallback, <think> robustness)")
    t0 = time.time()
    try:
        agent = Agent(model, output_type=PromptedOutput(Diagnosis))
        res = await agent.run(TRIAGE_PROMPT)
        ok = res.output.failure_class == "locator-drift"
        record("P3 PromptedOutput", ok, t0, f"{res.output.failure_class}/{res.output.confidence}")
    except Exception as e:
        record("P3 PromptedOutput", False, t0, f"{type(e).__name__}: {e}"[:200])


async def p4_tool_loop():
    print("P4 Exploration tool loop (agent calls query_dom)")
    t0 = time.time()
    calls: list[str] = []

    agent = Agent(
        model,
        output_type=Diagnosis,
        system_prompt="You diagnose Robot Framework failures. ALWAYS call query_dom to inspect the page before answering.",
    )

    @agent.tool
    async def query_dom(ctx: RunContext[None], css_selector: str) -> str:
        """Return count and outerHTML of elements matching a CSS selector."""
        calls.append(css_selector)
        if "signin" in css_selector or "submit" in css_selector or "button" in css_selector:
            return '1 match: <button id="signin-btn" type="submit">Sign in</button>'
        return "0 matches"

    try:
        res = await agent.run(
            "keyword: Click  args: ['id=login-button'] failed with: locator not found. "
            "The page is a login form. Diagnose the failure class (one of: locator-drift, timing, viewport, "
            "overlay, form-state, assertion-drift, unknown); confidence one of low/medium/high."
        )
        ok = len(calls) > 0 and res.output.failure_class == "locator-drift"
        record("P4 Tool loop", ok, t0, f"tool called {len(calls)}x with {calls[:3]}")
    except Exception as e:
        record("P4 Tool loop", False, t0, f"{type(e).__name__}: {e}"[:200])


async def p5_model_retry(output_mode: str):
    print(f"P5 ModelRetry via output_validator [{output_mode}]")
    t0 = time.time()
    attempts: list[str] = []

    class LocatorProposal(BaseModel):
        locator: str
        rationale: str

    out_type = LocatorProposal if output_mode == "tool" else PromptedOutput(LocatorProposal)
    agent = Agent(model, output_type=out_type, retries=3)

    @agent.output_validator
    async def verify(ctx: RunContext[None], out: LocatorProposal) -> LocatorProposal:
        attempts.append(out.locator)
        # Simulate live-session verification: first proposal is always "not unique"
        if len(attempts) == 1:
            raise ModelRetry(
                f"Verification against live page failed: locator '{out.locator}' matched 3 elements, "
                "need exactly 1. Propose a more specific locator using the id attribute."
            )
        if "signin-btn" not in out.locator and "user-email" not in out.locator:
            raise ModelRetry("Locator matched 0 elements. Use an id visible in the page excerpt.")
        return out

    try:
        res = await agent.run(
            f"Propose a CSS locator for the Sign in button on this page:\n{PAGE}\n"
            "Return the locator and a one-line rationale."
        )
        ok = len(attempts) >= 2
        record(f"P5 ModelRetry/{output_mode}", ok, t0, f"{len(attempts)} attempts -> {res.output.locator}")
    except Exception as e:
        record(f"P5 ModelRetry/{output_mode}", False, t0, f"{type(e).__name__}: {e}"[:200])


async def p6_realistic_healing():
    print("P6 Realistic locator healing (proposals + code-side verification)")
    t0 = time.time()

    class LocatorProposals(BaseModel):
        locators: list[str]

    agent = Agent(model, output_type=LocatorProposals)
    try:
        res = await agent.run(
            "You fix broken Robot Framework Browser locators.\n"
            "failed_locator: id=login-button\nkeyword: Click\n"
            f"page_source: {PAGE}\n"
            "Propose up to 3 alternative CSS locators, best first, each starting with 'css='."
        )
        # code-side verification stand-in: the real engine would query the live page
        good = [l for l in res.output.locators if "signin-btn" in l]
        record("P6 Healing", bool(good), t0, f"{len(res.output.locators)} proposals, valid: {good[:1]}")
    except Exception as e:
        record("P6 Healing", False, t0, f"{type(e).__name__}: {e}"[:200])


async def main():
    print(f"=== MiniMax probes, model={MODEL_NAME}, pydantic-ai 1.107.0 ===")
    await p1_tool_output()
    await p2_native_output()
    await p3_prompted_output()
    await p4_tool_loop()
    await p5_model_retry("tool")
    await p5_model_retry("prompted")
    await p6_realistic_healing()
    print("\n=== SUMMARY ===")
    for probe, status, dt, note in results:
        print(f"{status:4} {dt:6.1f}s  {probe:24} {note}")


if __name__ == "__main__":
    asyncio.run(main())
