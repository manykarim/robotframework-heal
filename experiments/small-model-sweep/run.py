"""Run the packaged sweep harness against OpenRouter (or any OpenAI-compatible backend).

The harness itself lives in ``heal.evals.sweep`` (packaged and unit-tested);
this is a thin, resumable runner. Each (model, mode) cell is written to the
output file as soon as it finishes, so a dropped host or an interrupted run
loses at most one cell.

Usage:
    uv run python experiments/small-model-sweep/run.py --limit 12
    uv run python experiments/small-model-sweep/run.py --models qwen/qwen3-8b --modes prompted
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from heal.core.settings import OutputMode  # noqa: E402
from heal.evals.corpus import load_corpus  # noqa: E402
from heal.evals.sweep import isolated_env, stratified_sample, sweep_cell  # noqa: E402
from models import MODELS, OPENROUTER_BASE_URL  # noqa: E402

FIXTURES = ROOT / "tests" / "evals" / "fixtures"


def load_key(name: str) -> str | None:
    """Read a key from the process env, falling back to the repo .env file."""
    import os

    if os.environ.get(name):
        return os.environ[name]
    env_file = ROOT / ".env"
    if not env_file.exists():
        return None
    for line in env_file.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("=")
        if key.strip() == name:
            return value.strip().strip("'\"") or None
    return None


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=OPENROUTER_BASE_URL)
    ap.add_argument("--api-key-var", default="OPENROUTER_API_KEY")
    ap.add_argument("--models", help="comma-separated subset of the curated list")
    ap.add_argument("--modes", default="prompted,native", help="output modes to compare")
    ap.add_argument("--limit", type=int, default=12, help="stratified fixture count (0 = all)")
    ap.add_argument("--out", default=str(Path(__file__).parent / "results.json"))
    args = ap.parse_args()

    api_key = load_key(args.api_key_var)
    if not api_key:
        sys.exit(f"no API key: set {args.api_key_var} in the environment or .env")

    models = [m for m, _b, _c in MODELS]
    if args.models:
        wanted = {m.strip() for m in args.models.split(",")}
        models = [m for m in models if m in wanted]
        if not models:
            sys.exit(f"no curated model matched {sorted(wanted)}")
    modes = [OutputMode(m.strip()) for m in args.modes.split(",")]

    corpus = load_corpus(FIXTURES)
    fixtures = stratified_sample(corpus, args.limit)
    suites = sorted({p.name.rsplit("-", 1)[0] for p, _ in fixtures})

    out_path = Path(args.out)
    cells: list[dict] = []
    if out_path.exists():  # resume: keep completed cells
        cells = json.loads(out_path.read_text(encoding="utf-8")).get("cells", [])
    done = {(c["model"], c["requested_mode"]) for c in cells}

    def flush() -> None:
        out_path.write_text(
            json.dumps(
                {
                    "base_url": args.base_url,
                    "fixtures": len(fixtures),
                    "fixture_names": [p.name for p, _ in fixtures],
                    "suites": suites,
                    "modes": [m.value for m in modes],
                    "cells": cells,
                },
                indent=1,
            ),
            encoding="utf-8",
        )

    print(
        f"sweep: {len(models)} models x {len(modes)} modes x {len(fixtures)} fixtures "
        f"from {len(suites)} suites @ {args.base_url}",
        flush=True,
    )

    with isolated_env() as stashed:
        if stashed:
            print(f"  (ignoring ambient {', '.join(stashed)})", flush=True)
        for model in models:
            for mode in modes:
                if (model, mode.value) in done:
                    print(f"-- {model} [{mode.value}] cached", flush=True)
                    continue
                print(f"-- {model} [{mode.value}] ...", flush=True)
                record = await sweep_cell(
                    model,
                    fixtures,
                    base_url=args.base_url,
                    api_key=api_key,
                    mode=mode,
                )
                cells.append(record)
                flush()
                if "accuracy_pct" in record:
                    print(
                        f"   engine={record['engine_output']} "
                        f"doctor={record.get('doctor_output')}/{record.get('doctor_tools')} "
                        f"acc={record['accuracy_pct']}% wrong={record['wrong_element']} "
                        f"err={record['errors']} med={record['median_seconds']}s "
                        f"{record['median_tokens']}tok",
                        flush=True,
                    )
                else:
                    print(f"   UNREACHABLE: {record.get('error')}", flush=True)

    print(f"\nwrote {out_path}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
