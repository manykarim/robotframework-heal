"""Small-model healing sweep against an Ollama (OpenAI-compatible) backend.

For each curated model: probe capabilities (heal doctor), then replay the
60-fixture eval corpus grading element identity. Records reachability, the
resolved output mode, accuracy %, median latency, median tokens and failure
modes; writes results.json. Host-configurable; skips unreachable models.

Usage:
    uv run python experiments/ollama-small-models/sweep.py [--host H:PORT]
                  [--models m1,m2] [--out results.json] [--limit N]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from bs4 import BeautifulSoup  # noqa: E402

from heal.core.doctor import run_doctor  # noqa: E402
from heal.core.engine import HealingEngine  # noqa: E402
from heal.core.runtime import AgentRuntime  # noqa: E402
from heal.core.schemas import EvidenceKind, OutcomeStatus  # noqa: E402
from heal.core.settings import HealSettings  # noqa: E402
from heal.evals.corpus import load_corpus, normalize_to_css  # noqa: E402
from heal.evals.replay import ReplaySession, builder_from_context  # noqa: E402
from models import OLLAMA_BASE_URL, SELECTION  # noqa: E402

FIXTURES = ROOT / "tests" / "evals" / "fixtures"
PER_FIXTURE_TIMEOUT = 120.0


def _settings(model: str, base_url: str) -> HealSettings:
    # selection tier is the default; api_key is a placeholder Ollama ignores
    return HealSettings(_env_file=None, model=model, base_url=base_url, api_key="ollama")


async def _heal_fixture(engine: HealingEngine, fixture) -> dict:
    ctx = fixture.context
    session = ReplaySession(ctx)
    t0 = time.time()
    try:
        event = await asyncio.wait_for(
            engine.handle(builder_from_context(ctx), session), timeout=PER_FIXTURE_TIMEOUT
        )
    except Exception as exc:
        return {"ok": False, "status": "error", "seconds": time.time() - t0,
                "tokens": 0, "detail": f"{type(exc).__name__}: {exc}"[:120]}
    out = event.outcome
    correct = False
    if out.status is OutcomeStatus.HEALED and out.healed_locator:
        dom = ctx.evidence_of(EvidenceKind.DOM_EXCERPT)
        soup = BeautifulSoup(dom.excerpt if dom else "", "html.parser")
        css = normalize_to_css(out.healed_locator)
        try:
            got = soup.select(css) if css else []
        except Exception:
            got = []
        truth = soup.select(fixture.truth_css)
        correct = bool(truth and len(got) == 1 and got[0] is truth[0])
    return {"ok": correct, "status": out.status.value, "seconds": time.time() - t0,
            "tokens": out.usage.total_tokens, "detail": "" if correct else out.detail[:120]}


async def sweep_model(model: str, bucket: str, base_url: str, fixtures) -> dict:
    rec: dict = {"model": model, "bucket": bucket}
    settings = _settings(model, base_url)
    runtime = AgentRuntime(settings)
    # capabilities probe
    try:
        report = await run_doctor(runtime.model("locator"), model_name=model, include_vision=False)
        caps = report.capabilities()
        rec["reachable"] = report.reachable
        rec["doctor"] = {r.name: ("PASS" if r.ok else "FAIL") for r in report.results}
        rec["resolved_output"] = caps.structured_output.value
        rec["resolved_tools"] = caps.tools.value
    except Exception as exc:
        rec["reachable"] = False
        rec["error"] = f"doctor: {type(exc).__name__}: {exc}"[:140]
        return rec
    if not report.reachable:
        rec["error"] = "; ".join(report.recommendations())[:160]
        return rec
    # corpus replay
    engine = HealingEngine(runtime)
    results = []
    for _path, fixture in fixtures:
        results.append(await _heal_fixture(engine, fixture))
    n = len(results)
    correct = sum(1 for r in results if r["ok"])
    errors = [r for r in results if r["status"] == "error"]
    rec["fixtures"] = n
    rec["accuracy_pct"] = round(100 * correct / n, 1) if n else 0
    rec["errors"] = len(errors)
    rec["median_seconds"] = round(statistics.median(r["seconds"] for r in results), 1) if n else 0
    healed_tokens = [r["tokens"] for r in results if r["tokens"]]
    rec["median_tokens"] = int(statistics.median(healed_tokens)) if healed_tokens else 0
    # collect distinct failure detail signatures
    fails = {}
    for r in results:
        if not r["ok"] and r["detail"]:
            sig = r["detail"].split(":")[0][:60]
            fails[sig] = fails.get(sig, 0) + 1
    rec["failure_modes"] = dict(sorted(fails.items(), key=lambda x: -x[1])[:5])
    return rec


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host")
    ap.add_argument("--models")
    ap.add_argument("--out", default=str(Path(__file__).parent / "results.json"))
    ap.add_argument("--limit", type=int, default=0, help="limit fixtures (smoke)")
    args = ap.parse_args()

    base_url = f"http://{args.host}/v1" if args.host else OLLAMA_BASE_URL
    selection = SELECTION
    if args.models:
        wanted = set(args.models.split(","))
        selection = [s for s in SELECTION if s[0] in wanted]

    fixtures = load_corpus(FIXTURES)
    if args.limit:
        fixtures = fixtures[: args.limit]
    print(f"sweep: {len(selection)} models x {len(fixtures)} fixtures @ {base_url}", flush=True)

    records = []
    for model, bucket, _et, _v in selection:
        print(f"-- {model} ({bucket}) ...", flush=True)
        rec = await sweep_model(model, bucket, base_url, fixtures)
        records.append(rec)
        if rec.get("reachable") and "accuracy_pct" in rec:
            print(f"   out={rec['resolved_output']} acc={rec['accuracy_pct']}% "
                  f"err={rec['errors']} med={rec['median_seconds']}s {rec['median_tokens']}tok "
                  f"fails={rec.get('failure_modes')}", flush=True)
        else:
            print(f"   UNREACHABLE/ERROR: {rec.get('error', rec.get('doctor'))}", flush=True)

    out = {"base_url": base_url, "fixtures": len(fixtures), "models": records}
    Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"\nwrote {args.out}", flush=True)
    print(f"\n{'model':24} {'out':9} {'acc%':>5} {'err':>4} {'med_s':>6} {'tok':>6}  fails", flush=True)
    for r in records:
        if r.get("reachable") and "accuracy_pct" in r:
            print(f"{r['model']:24} {r['resolved_output']:9} {r['accuracy_pct']:5} {r['errors']:4} "
                  f"{r['median_seconds']:6} {r['median_tokens']:6}  {r.get('failure_modes')}", flush=True)
        else:
            print(f"{r['model']:24} {'—':9} unreachable/error", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
