"""Selection mode vs generation mode on REAL recorded healing transactions.

For each recorded locator-drift heal (ground truth = the verified healed
locator), compare:
  A) generation mode (current): simplified DOM in prompt, model writes locators
  B) selection mode: deterministic candidates from the DOM (dom.generate_proposals)
     + element info; model returns an index (flat schema)

Measures: prompt chars, candidate-generation time, correctness (chosen element
IS the ground-truth element in the recorded DOM), latency.
"""
import asyncio
import glob
import json
import os
import sys
import time
from pathlib import Path

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.output import PromptedOutput
from pydantic_ai.providers.openai import OpenAIProvider

load_dotenv(Path(__file__).parents[2] / ".env")
sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from heal.core.schemas import EvidenceKind, LocatorProposals  # noqa: E402
from heal.drivers.dom import generate_proposals  # noqa: E402
from heal.report.store import load_events  # noqa: E402

provider = OpenAIProvider(
    base_url=os.environ["OPENROUTER_BASE_URL"], api_key=os.environ["OPENROUTER_API_KEY"]
)
MODELS = ["openai/gpt-4.1-nano", "google/gemini-2.5-flash-lite", "meta-llama/llama-3.1-8b-instruct"]

KEYWORD_TAGS = {
    "click": ["button", "a", "input", "label", "li"],
    "fill": ["input", "textarea"],
    "type": ["input", "textarea"],
    "select options": ["select"],
    "wait for elements state": ["button", "a", "input", "label", "li", "div", "span"],
}


def tags_for(keyword):
    kw = keyword.lower()
    for marker, tags in KEYWORD_TAGS.items():
        if marker in kw:
            return tags
    return ["button", "a", "input", "select", "label", "li", "span"]


def collect_cases():
    cases, seen = [], set()
    for path in glob.glob("results/*/heal/events.jsonl"):
        for e in load_events(path):
            if not (e.outcome and e.outcome.healed_locator and e.context):
                continue
            dom = e.context.evidence_of(EvidenceKind.DOM_EXCERPT)
            if not dom or not dom.excerpt:
                continue
            key = (e.context.failed_locator, e.outcome.healed_locator)
            if key in seen:
                continue
            seen.add(key)
            css = e.outcome.healed_locator
            for p in ("css=", "id="):
                if css.startswith(p):
                    css = ("#" + css[3:]) if p == "id=" else css[4:]
                    break
            else:
                continue  # xpath ground truth: bs4 can't resolve, skip
            css = css.replace(":visible", "").replace(" >> nth=0", "")
            soup = BeautifulSoup(dom.excerpt, "html.parser")
            try:
                matches = soup.select(css)
            except Exception:
                continue
            if len(matches) != 1:
                continue
            cases.append({
                "suite": e.suite_name.split(".")[-1], "keyword": e.keyword.name,
                "failed": e.context.failed_locator, "truth_css": css,
                "dom": dom.excerpt,
            })
    return cases


class Pick(BaseModel):
    index: int
    reason: str = ""


async def run_case(case, model_name, results):
    model = OpenAIChatModel(model_name, provider=provider)
    soup = BeautifulSoup(case["dom"], "html.parser")
    truth = soup.select(case["truth_css"])[0]

    # ---- A: generation mode
    gen_prompt = (
        f"You repair broken locators for Robot Framework tests.\n"
        f"failed_locator: {case['failed']}\nkeyword: {case['keyword']}\n"
        f"page_source:\n```html\n{case['dom']}\n```\n"
        "Propose up to 3 CSS locators (prefix 'css=') for the intended element, best first."
    )
    agent = Agent(model, output_type=PromptedOutput(LocatorProposals), retries=1)
    t0 = time.time()
    try:
        res = await agent.run(gen_prompt)
        ok = False
        for loc in res.output.locators[:3]:
            css = loc.removeprefix("css=").replace(":visible", "").replace(" >> nth=0", "")
            try:
                m = soup.select(css)
            except Exception:
                continue
            if len(m) == 1 and m[0] is truth:
                ok = True
                break
        results.append((model_name, case["suite"], "GEN", ok, time.time() - t0, len(gen_prompt)))
    except Exception:
        results.append((model_name, case["suite"], "GEN", None, time.time() - t0, len(gen_prompt)))

    # ---- B: selection mode
    t_gen = time.time()
    candidates = generate_proposals(case["dom"], tags_for(case["keyword"]))
    gen_seconds = time.time() - t_gen
    infos, truth_index = [], None
    for i, cand in enumerate(candidates):
        css = cand.removeprefix("css=")
        try:
            el = soup.select(css)[0]
        except Exception:
            continue
        infos.append({"index": i, "locator": cand, "tag": el.name,
                      "text": el.get_text(strip=True)[:60],
                      "attrs": {k: str(v)[:40] for k, v in list(el.attrs.items())[:4]}})
        if el is truth:
            truth_index = i
    sel_prompt = (
        f"A Robot Framework locator broke.\nfailed_locator: {case['failed']}\n"
        f"keyword: {case['keyword']}\n"
        f"Pick the candidate that matches the test's intent. Respond with its index.\n"
        f"candidates:\n{json.dumps(infos)}"
    )
    if truth_index is None:
        results.append((model_name, case["suite"], "SEL", "no-cand", gen_seconds, len(sel_prompt)))
        return
    agent = Agent(model, output_type=PromptedOutput(Pick), retries=1)
    t0 = time.time()
    try:
        res = await agent.run(sel_prompt)
        ok = res.output.index == truth_index
        results.append((model_name, case["suite"], "SEL", ok, time.time() - t0, len(sel_prompt)))
    except Exception:
        results.append((model_name, case["suite"], "SEL", None, time.time() - t0, len(sel_prompt)))


async def main():
    os.chdir(Path(__file__).parents[2])
    cases = collect_cases()
    print(f"{len(cases)} unique ground-truth cases from run stores", flush=True)
    results = []
    for case in cases:
        for m in MODELS:
            await run_case(case, m, results)
        print(f"done: {case['suite']} / {case['failed']}", flush=True)
    print("\nmodel                                  mode   ok  err  acc%   avg_s  avg_prompt_chars", flush=True)
    for m in MODELS:
        for mode in ("GEN", "SEL"):
            rows = [r for r in results if r[0] == m and r[2] == mode and r[3] != "no-cand"]
            oks = [r for r in rows if r[3] is True]
            errs = [r for r in rows if r[3] is None]
            if rows:
                acc = 100 * len(oks) / len(rows)
                avg_s = sum(r[4] for r in rows) / len(rows)
                avg_p = sum(r[5] for r in rows) / len(rows)
                print(f"{m:38} {mode}  {len(oks):3} {len(errs):3}  {acc:5.0f}  {avg_s:6.1f}  {avg_p:8.0f}", flush=True)
    nc = {r[1] for r in results if r[3] == "no-cand"}
    print(f"\nsuites where the deterministic generator missed the truth element: {sorted(nc)}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
