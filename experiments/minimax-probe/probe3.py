"""Probe 3: capability matrix across small/cheap OpenRouter models.

Same core probes as probe.py, parametrized over models, default pydantic-ai
profile (what a user gets out of the box pointing base_url at OpenRouter).
Probes per model:
  A ToolOutput triage      (structured output via tool call)
  B PromptedOutput triage  (universal fallback)
  C Tool loop              (exploration tool gets called and used)
  D ModelRetry/prompted    (verification feedback loop, prompted mode)
"""

import asyncio
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.output import PromptedOutput
from pydantic_ai.providers.openai import OpenAIProvider

load_dotenv(Path(__file__).parents[2] / ".env")

MODELS = [
    "openai/gpt-4.1-nano",
    "google/gemini-2.5-flash-lite",
    "qwen/qwen3-14b",
    "mistralai/ministral-8b",
    "meta-llama/llama-3.1-8b-instruct",
]

provider = OpenAIProvider(
    base_url=os.environ["OPENROUTER_BASE_URL"],
    api_key=os.environ["OPENROUTER_API_KEY"],
)


class Diagnosis(BaseModel):
    failure_class: str
    confidence: str
    rationale: str


class LocatorProposal(BaseModel):
    locator: str
    rationale: str


PAGE = """<html><body><form id="login-form">
<label for="user-email">Email</label><input id="user-email" type="text"/>
<label for="user-pass">Password</label><input id="user-pass" type="password"/>
<button id="signin-btn" type="submit">Sign in</button></form></body></html>"""

TRIAGE_PROMPT = (
    "A Robot Framework keyword failed.\n"
    "keyword: Click  args: ['id=login-button']\n"
    "error: TimeoutError waiting for locator('id=login-button')\n"
    f"page excerpt: {PAGE}\n"
    "Classify: failure_class in [locator-drift, timing, viewport, overlay, form-state, assertion-drift, unknown]; "
    "confidence in [low, medium, high]."
)

rows = []


async def run_probe(model_name: str, probe: str):
    model = OpenAIChatModel(model_name, provider=provider)
    t0 = time.time()
    try:
        if probe == "A":
            agent = Agent(model, output_type=Diagnosis)
            res = await agent.run(TRIAGE_PROMPT)
            ok, note = res.output.failure_class == "locator-drift", res.output.failure_class
        elif probe == "B":
            agent = Agent(model, output_type=PromptedOutput(Diagnosis))
            res = await agent.run(TRIAGE_PROMPT)
            ok, note = res.output.failure_class == "locator-drift", res.output.failure_class
        elif probe == "C":
            calls = []
            agent = Agent(model, output_type=Diagnosis,
                          system_prompt="Diagnose RF failures. ALWAYS call query_dom before answering.")

            @agent.tool
            async def query_dom(ctx: RunContext[None], css_selector: str) -> str:
                """Return match count and HTML for a CSS selector."""
                calls.append(css_selector)
                if any(k in css_selector for k in ("button", "signin", "submit")):
                    return '1 match: <button id="signin-btn" type="submit">Sign in</button>'
                return "0 matches"

            res = await agent.run(
                "Click on 'id=login-button' failed: locator not found (login form page). "
                "Diagnose failure_class/confidence.")
            ok = len(calls) > 0 and res.output.failure_class == "locator-drift"
            note = f"tool {len(calls)}x"
        elif probe == "D":
            attempts = []
            agent = Agent(model, output_type=PromptedOutput(LocatorProposal), retries=3)

            @agent.output_validator
            async def verify(ctx: RunContext[None], out: LocatorProposal) -> LocatorProposal:
                attempts.append(out.locator)
                if len(attempts) == 1:
                    raise ModelRetry(
                        f"Locator '{out.locator}' matched 3 elements, need exactly 1. "
                        "Propose a more specific locator using the id attribute.")
                if "signin-btn" not in out.locator and "user-email" not in out.locator:
                    raise ModelRetry("Locator matched 0 elements. Use an id from the page excerpt.")
                return out

            res = await agent.run(
                f"Propose a CSS locator for the Sign in button:\n{PAGE}\nReturn locator + one-line rationale.")
            ok, note = len(attempts) >= 2, f"{len(attempts)} attempts -> {res.output.locator}"
        rows.append((model_name, probe, "PASS" if ok else "FAIL", time.time() - t0, note))
    except Exception as e:
        rows.append((model_name, probe, "ERR", time.time() - t0, f"{type(e).__name__}: {e}"[:130]))
    print(f"  {rows[-1]}", flush=True)


async def main():
    print("=== probe3: OpenRouter small-model matrix ===", flush=True)
    for m in MODELS:
        print(f"-- {m}", flush=True)
        for p in ("A", "B", "C", "D"):
            await run_probe(m, p)
    print("\n=== MATRIX (rows: model, cols: A=ToolOutput B=Prompted C=ToolLoop D=Retry) ===", flush=True)
    for m in MODELS:
        cells = {p: s for (mm, p, s, _, _) in rows if mm == m}
        print(f"{m:38} " + "  ".join(f"{p}:{cells.get(p,'-'):4}" for p in "ABCD"), flush=True)
    for r in rows:
        print(r, flush=True)


if __name__ == "__main__":
    asyncio.run(main())
