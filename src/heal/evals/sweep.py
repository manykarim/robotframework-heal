"""Cross-model healing sweep: replay the corpus against any OpenAI-compatible backend.

Implements the ``model-compatibility-report`` capability. For each (model,
output mode) cell: probe capabilities via ``heal doctor``, then replay a sample
of the eval corpus grading **element identity** — a heal counts only when the
proposed locator resolves to exactly the recorded ground-truth node.

Three properties the first (Ollama) generation of this harness lacked, each of
which produced a misleading number:

* **Stratified sampling.** Taking the first N fixtures drew 11 of 12 from a
  single suite, with the same scenario repeated three times. :func:`stratified_sample`
  spreads across suites and drops duplicate actions first.
* **Per-fixture records.** Only aggregates were kept, so a fixture later found
  to be bad could not be excluded without re-running every model.
* **RCA-free latency.** Root-cause analysis fires on every *unhealed* keyword,
  inside the measured wall clock but outside the token count — so weak models
  were charged for a round-trip strong models never made. ``median_seconds``
  covers healed fixtures only; ``median_seconds_all`` keeps the raw figure.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import statistics
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Iterable, Sequence

from bs4 import BeautifulSoup

from ..core.doctor import run_doctor
from ..core.engine import HealingEngine
from ..core.runtime import AgentRuntime
from ..core.schemas import EvidenceKind, OutcomeStatus
from ..core.settings import HealSettings, OutputMode
from .corpus import Fixture, normalize_to_css, truth_scope
from .replay import ReplaySession, builder_from_context

#: Wall-clock cap per fixture; a hung backend must not stall the whole sweep.
PER_FIXTURE_TIMEOUT = 120.0


def _suite_of(path: Path) -> str:
    """Suite prefix of a fixture filename ("ait-llm-<hash>.fixture.json")."""
    return path.name.rsplit("-", 1)[0]


def stratified_sample(
    corpus: Sequence[tuple[Path, Fixture]], limit: int = 0
) -> list[tuple[Path, Fixture]]:
    """Up to ``limit`` fixtures spread across suites, duplicate actions dropped.

    Deterministic (no RNG): fixtures are deduplicated by :func:`truth_scope` so
    the same keyword+args+locator is graded once, then drawn round-robin across
    suites so no single suite dominates. ``limit=0`` returns the whole
    deduplicated corpus.
    """
    by_suite: OrderedDict[str, list[tuple[Path, Fixture]]] = OrderedDict()
    seen_scopes: set[tuple] = set()
    for path, fixture in corpus:
        scope = truth_scope(fixture)
        if scope in seen_scopes:
            continue  # same action already represented
        seen_scopes.add(scope)
        by_suite.setdefault(_suite_of(path), []).append((path, fixture))

    picked: list[tuple[Path, Fixture]] = []
    queues = list(by_suite.values())
    while queues and (not limit or len(picked) < limit):
        for queue in list(queues):
            if limit and len(picked) >= limit:
                break
            if queue:
                picked.append(queue.pop(0))
            if not queue:
                queues.remove(queue)
    return picked


def grade(fixture: Fixture, healed_locator: str | None) -> bool:
    """Element identity: did the heal land on the recorded ground-truth node?

    Deliberately strict — a locator that is unique and visible but points at a
    different element is *not* a heal. Verification cannot catch that (the
    corpus itself once recorded such a heal as truth), so grading must.
    """
    if not healed_locator:
        return False
    dom = fixture.context.evidence_of(EvidenceKind.DOM_EXCERPT)
    soup = BeautifulSoup(dom.excerpt if dom else "", "html.parser")
    css = normalize_to_css(healed_locator)
    try:
        got = soup.select(css) if css else []
        truth = soup.select(fixture.truth_css)
    except Exception:
        return False
    return bool(truth and len(got) == 1 and got[0] is truth[0])


@contextlib.contextmanager
def isolated_env():
    """Drop ambient ``HEAL_*`` vars so a sweep measures what it configured.

    ``HealSettings(_env_file=None)`` only disables the dotenv file; process
    environment still wins. An exported ``HEAL_LOCATOR_MODEL`` would silently
    sweep a different model than the record is labelled with.
    """
    stashed = {k: v for k, v in os.environ.items() if k.startswith("HEAL_")}
    for key in stashed:
        del os.environ[key]
    try:
        yield sorted(stashed)
    finally:
        os.environ.update(stashed)


def sweep_settings(model: str, base_url: str | None, api_key: str | None, mode: OutputMode):
    return HealSettings(
        _env_file=None,
        model=model,
        base_url=base_url,
        api_key=api_key or "placeholder",
        output_mode=mode,
    )


async def heal_fixture(engine: HealingEngine, fixture: Fixture) -> dict[str, Any]:
    """Replay one fixture; never raises — a dead backend is data, not a crash."""
    ctx = fixture.context
    started = time.monotonic()
    try:
        event = await asyncio.wait_for(
            engine.handle(builder_from_context(ctx), ReplaySession(ctx)),
            timeout=PER_FIXTURE_TIMEOUT,
        )
    except Exception as exc:
        return {
            "ok": False,
            "status": "error",
            "seconds": round(time.monotonic() - started, 2),
            "tokens": 0,
            "requests": 0,
            "detail": f"{type(exc).__name__}: {exc}"[:160],
        }
    outcome = event.outcome
    healed = outcome.status is OutcomeStatus.HEALED
    ok = grade(fixture, outcome.healed_locator) if healed else False
    return {
        "ok": ok,
        "status": outcome.status.value,
        # a healed-but-wrong-element result is the interesting failure mode
        "wrong_element": healed and not ok,
        "seconds": round(time.monotonic() - started, 2),
        "tokens": outcome.usage.total_tokens,
        "requests": outcome.usage.requests,
        "detail": "" if ok else outcome.detail[:160],
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-fixture records, keeping RCA out of the headline latency."""
    total = len(results)
    healed = [r for r in results if r["status"] == "healed"]
    correct = [r for r in results if r["ok"]]
    tokens = [r["tokens"] for r in results if r["tokens"]]
    failure_modes: dict[str, int] = {}
    for r in results:
        if not r["ok"] and r["detail"]:
            sig = r["detail"].split(":")[0][:60]
            failure_modes[sig] = failure_modes.get(sig, 0) + 1
    return {
        "fixtures": total,
        "accuracy_pct": round(100 * len(correct) / total, 1) if total else 0.0,
        "wrong_element": sum(1 for r in results if r.get("wrong_element")),
        "errors": sum(1 for r in results if r["status"] == "error"),
        # healed fixtures never trigger RCA, so this column is comparable
        # across models; the raw figure is kept for reference
        "median_seconds": round(statistics.median(r["seconds"] for r in healed), 1) if healed else None,
        "median_seconds_all": round(statistics.median(r["seconds"] for r in results), 1) if total else None,
        "median_tokens": int(statistics.median(tokens)) if tokens else 0,
        "failure_modes": dict(sorted(failure_modes.items(), key=lambda kv: -kv[1])[:5]),
    }


async def sweep_cell(
    model: str,
    fixtures: Sequence[tuple[Path, Fixture]],
    *,
    base_url: str | None,
    api_key: str | None,
    mode: OutputMode = OutputMode.AUTO,
    probe: bool = True,
    on_fixture=None,
) -> dict[str, Any]:
    """One (model, output-mode) cell: probe, then replay every fixture."""
    record: dict[str, Any] = {"model": model, "requested_mode": mode.value}
    runtime = AgentRuntime(sweep_settings(model, base_url, api_key, mode))
    caps = runtime.capabilities("locator")
    record["engine_output"] = caps.structured_output.value
    record["engine_tools"] = caps.tools.value

    if probe:
        try:
            report = await run_doctor(runtime.model("locator"), model_name=model, include_vision=False)
        except Exception as exc:
            record.update(reachable=False, error=f"doctor: {type(exc).__name__}: {exc}"[:160])
            return record
        probed = report.capabilities()
        record["reachable"] = report.reachable
        record["doctor"] = {r.name: ("PASS" if r.ok else "FAIL") for r in report.results}
        record["doctor_output"] = probed.structured_output.value
        record["doctor_tools"] = probed.tools.value
        if not report.reachable:
            record["error"] = "; ".join(report.recommendations())[:160]
            return record
    else:
        record["reachable"] = True

    engine = HealingEngine(runtime)
    results = []
    for path, fixture in fixtures:
        result = await heal_fixture(engine, fixture)
        result["fixture"] = path.name
        results.append(result)
        if on_fixture:
            on_fixture(result)
    # what healing ACTUALLY used: the runtime's safety rule may have corrected
    # the configured mode mid-run, and a record that hides that is misleading
    effective = runtime.capabilities("locator")
    record["effective_output"] = effective.structured_output.value
    record["mode_corrected"] = effective.structured_output is not caps.structured_output
    if runtime.capability_notes:
        record["capability_notes"] = list(runtime.capability_notes)

    record["per_fixture"] = results  # keep raw records: aggregates can be redone
    record.update(summarize(results))
    return record


async def run_sweep(
    models: Iterable[str],
    fixtures: Sequence[tuple[Path, Fixture]],
    *,
    base_url: str | None,
    api_key: str | None,
    modes: Sequence[OutputMode] = (OutputMode.AUTO,),
    on_cell=None,
) -> dict[str, Any]:
    """Sweep every (model, mode) cell. Unreachable cells are recorded, not fatal."""
    cells = []
    for model in models:
        for mode in modes:
            record = await sweep_cell(
                model, fixtures, base_url=base_url, api_key=api_key, mode=mode
            )
            cells.append(record)
            if on_cell:
                on_cell(record)
    return {
        "base_url": base_url,
        "fixtures": len(fixtures),
        "fixture_names": [p.name for p, _ in fixtures],
        "modes": [m.value for m in modes],
        "cells": cells,
    }
