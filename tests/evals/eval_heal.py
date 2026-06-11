"""Healing-quality evals over the harvested ground-truth corpus (replay, no browser).

Usage (any backend; prefer small/cheap models):
    uv run python tests/evals/eval_heal.py [--model M] [--base-url U] [--api-key K] [--tiers selection|generation]

CLI flags override everything (incl. the auto-loaded .env — which otherwise
wins over process env vars by design). Grading is element-identity: a heal
only counts when the produced locator resolves to the SAME element as the
recorded ground truth in the recorded DOM.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from bs4 import BeautifulSoup

from heal.core.engine import HealingEngine
from heal.core.runtime import AgentRuntime
from heal.core.schemas import EvidenceKind, OutcomeStatus
from heal.core.settings import HealSettings
from heal.evals.corpus import load_corpus, normalize_to_css
from heal.evals.replay import ReplaySession, builder_from_context

FIXTURES = Path(__file__).parent / "fixtures"


async def evaluate(fixture, engine: HealingEngine):
    ctx = fixture.context
    session = ReplaySession(ctx)
    event = await engine.handle(builder_from_context(ctx), session)
    outcome = event.outcome
    healed = outcome.status is OutcomeStatus.HEALED
    correct = False
    if healed and outcome.healed_locator:
        dom = ctx.evidence_of(EvidenceKind.DOM_EXCERPT)
        soup = BeautifulSoup(dom.excerpt if dom else "", "html.parser")
        truth = soup.select(fixture.truth_css)
        css = normalize_to_css(outcome.healed_locator)
        try:
            got = soup.select(css) if css else []
        except Exception:
            got = []
        correct = bool(truth and len(got) == 1 and got[0] is truth[0])
    return {
        "diagnosis": outcome.diagnosis.failure_class.value,
        "diagnosis_ok": outcome.diagnosis.failure_class.value == fixture.expected_class,
        "healed": healed,
        "correct_element": correct,
        "healed_locator": outcome.healed_locator,
        "tokens": outcome.usage.total_tokens,
        "seconds": round(outcome.duration_seconds, 1),
    }


def parse_overrides() -> dict:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model")
    parser.add_argument("--base-url", dest="base_url")
    parser.add_argument("--api-key", dest="api_key")
    parser.add_argument("--tiers", dest="locator_tiers", choices=["selection", "generation"])
    args = parser.parse_args()
    return {k: v for k, v in vars(args).items() if v is not None}


async def main():
    settings = HealSettings(**parse_overrides())
    if not settings.model:
        print("set HEAL_MODEL (and HEAL_BASE_URL/HEAL_API_KEY) to run evals", file=sys.stderr)
        raise SystemExit(2)
    corpus = load_corpus(FIXTURES)
    if not corpus:
        print(f"no fixtures in {FIXTURES} — run `heal corpus <results-paths>` first", file=sys.stderr)
        raise SystemExit(2)
    engine = HealingEngine(AgentRuntime(settings))
    results = []
    for path, fixture in corpus:
        result = await evaluate(fixture, engine)
        result["fixture"] = path.name
        results.append(result)
        print(json.dumps(result), flush=True)

    n = len(results)
    correct = sum(1 for r in results if r["correct_element"])
    diagnosed = sum(1 for r in results if r["diagnosis_ok"])
    tokens = sum(r["tokens"] for r in results)
    print(
        f"\nmodel={settings.model} tiers={settings.locator_tiers}: "
        f"correct-element {correct}/{n} ({100*correct/n:.0f}%), "
        f"diagnosis {diagnosed}/{n}, total tokens {tokens}"
    )
    raise SystemExit(0 if correct == n else 1)


if __name__ == "__main__":
    asyncio.run(main())
