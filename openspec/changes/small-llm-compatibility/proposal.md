# Proposal: small-llm-compatibility

## Why

robotframework-heal claims small self-hosted models work via a prompted-JSON floor, but that claim rests on a handful of probe data points (OpenRouter gpt-4.1-nano / gemini-flash-lite / one llama-8B run). It has never been exercised against a real fleet of locally-hosted small models with genuinely mixed capabilities — some with reliable tool calling, some with none, some non-English-tuned, some that emit `<think>` blocks or markdown-fenced JSON. A reachable Ollama instance (`192.168.1.15:11434`, v0.15.4, 18 models) is the ideal proving ground to find where healing actually breaks on small models and fix it.

The deliverable is twofold: a **reproducible cross-model compatibility sweep** that quantifies healing on each model, and the **small-model robustness fixes** the sweep surfaces (output-mode resolution, Ollama presets, schema/parse tolerance, doctor accuracy).

## What Changes

- **Probe the Ollama fleet** and curate a test selection covering the relevant axes: size (3B → 14B), tool-calling (e.g. `llama3.1`, `qwen3`, `granite3.2` with tools vs `phi3`, `phi4-mini`, `gemma3` without), and one vision model (`llama3.2-vision`).
- **A reproducible sweep harness**: run the healing eval corpus (offline replay — no browser, fast) across a configurable model list against any OpenAI-compatible backend, plus a small set of live-browser smoke heals; capture per model: reachability, `heal doctor` capabilities, resolved output mode, healing accuracy (element-identity), latency, tokens, and concrete failure modes.
- **A structured compatibility report** (per-model matrix + a written issues log) committed under `experiments/ollama-small-models/`, distinguishing engine bugs from model-quality limits.
- **Fix the tractable issues the sweep finds** in `model-runtime`: an Ollama backend preset (base-URL detection, capability defaults, unsupported-parameter stripping), per-model tool-support resolution that trusts the `doctor` probe, and parse/schema tolerance for small-model quirks (`<think>` blocks, fenced JSON, near-miss JSON) without weakening verification.
- **Re-run the sweep after fixes** and record the before/after delta, so the improvement is measured, not asserted.

## Capabilities

### New Capabilities

- `model-compatibility-report`: a reproducible sweep that evaluates healing across a list of models on a backend and emits a structured per-model compatibility report (capabilities, accuracy, latency, tokens, failure modes).

### Modified Capabilities

- `model-runtime`: Ollama-aware capability resolution and small-model robustness — an Ollama backend preset, per-model tool-support resolution driven by the doctor probe, and tolerance for small-model output quirks in the prompted/structured-output path.

## Impact

- **Code**: `src/heal/core/runtime.py` (Ollama preset, capability resolution), possibly `src/heal/core/doctor.py` (per-model probing nuances) and the prompted-output handling; a new sweep runner under `experiments/ollama-small-models/` reusing `heal.evals`.
- **Config/docs**: document the Ollama setup (`HEAL_BASE_URL=http://host:11434/v1`) in the model-providers guide; add the small-model compatibility matrix to the docs benchmarks.
- **Dependencies**: none (Ollama is reached over its OpenAI-compatible HTTP endpoint).
- **Tests**: unit tests for the new Ollama preset and any parse-tolerance logic (offline, with `TestModel`/`FunctionModel`); the sweep itself is gated behind a reachable Ollama host and is not part of PR CI.
- **Risk**: model-quality failures could be misread as engine bugs → the report explicitly separates the two and verification stays in output validators (a wrong-but-plausible heal still cannot pass); the Ollama host is a fixed lab address → the harness is host-configurable and skips when unreachable.
