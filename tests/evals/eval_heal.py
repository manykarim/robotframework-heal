"""Healing quality evals over golden failure fixtures (replay, no browser).

Usage (any backend; prefer small/cheap models):
    HEAL_MODEL=... HEAL_BASE_URL=... HEAL_API_KEY=... uv run python tests/evals/eval_heal.py

Measures per fixture: triage classification accuracy and locator-heal success
(verified proposal that resolves on the recorded DOM + successful replay
rerun). This is the per-model row of the compatibility matrix.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

from heal.core.engine import HealingEngine
from heal.core.runtime import AgentRuntime
from heal.core.schemas import OutcomeStatus
from heal.core.settings import HealSettings
from heal.evals.replay import ReplaySession, builder_from_context, load_fixture

FIXTURES = Path(__file__).parent / "fixtures"
#: fixture name -> (expected failure class, expect heal?)
EXPECTATIONS = {
    "locator_drift_login.json": ("locator-drift", True),
}


async def evaluate(fixture_path: Path, expected_class: str, expect_heal: bool, engine: HealingEngine):
    ctx = load_fixture(fixture_path)
    session = ReplaySession(ctx)
    start = time.time()
    event = await engine.handle(builder_from_context(ctx), session)
    elapsed = time.time() - start
    diagnosis_ok = event.outcome.diagnosis.failure_class.value == expected_class
    heal_ok = (event.outcome.status is OutcomeStatus.HEALED) == expect_heal
    return {
        "fixture": fixture_path.name,
        "diagnosis": event.outcome.diagnosis.failure_class.value,
        "diagnosis_ok": diagnosis_ok,
        "status": event.outcome.status.value,
        "heal_ok": heal_ok,
        "healed_locator": event.outcome.healed_locator,
        "seconds": round(elapsed, 1),
        "tokens": event.outcome.usage.total_tokens,
    }


async def main():
    settings = HealSettings()
    if not settings.model:
        print("set HEAL_MODEL (and HEAL_BASE_URL/HEAL_API_KEY) to run evals", file=sys.stderr)
        raise SystemExit(2)
    engine = HealingEngine(AgentRuntime(settings))
    results = []
    for name, (expected_class, expect_heal) in EXPECTATIONS.items():
        results.append(await evaluate(FIXTURES / name, expected_class, expect_heal, engine))
        print(json.dumps(results[-1]), flush=True)
    passed = sum(1 for r in results if r["diagnosis_ok"] and r["heal_ok"])
    print(f"\n{passed}/{len(results)} fixtures fully passed (model={settings.model})")
    raise SystemExit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    asyncio.run(main())
