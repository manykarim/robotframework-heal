# Design: small-llm-compatibility

## Context

The engine resolves model capability per role from `BACKEND_PRESETS` (currently MiniMax, vLLM, OpenRouter), explicit settings, or a `heal doctor` probe (tool / native / prompted / vision), then `build_agent(role, schema)` wraps the output in the resolved mode. Verification always lives in output validators, so it works in every mode — the prompted-JSON floor is what makes small models viable. Experiments to date (`experiments/minimax-probe`, `experiments/selection-mode`) cover hosted small models but not a self-hosted Ollama fleet with mixed tool support.

A reachable Ollama instance is available: `192.168.1.15:11434` (Ollama 0.15.4), OpenAI-compatible at `/v1`, 18 models spanning 3.2B–23.6B. Ollama's tool-calling support is per-model (e.g. `llama3.1`, `qwen3`, `granite3.2`, `llama3.2` advertise tools; `phi3`, `phi4-mini`, `gemma3` do not, or unreliably), making it an ideal capability spread.

This change follows the project's experiments-first norm: **sweep → analyse → fix → re-sweep → report.**

## Goals / Non-Goals

**Goals:**
- A reproducible, host-configurable sweep that measures healing per model and produces a structured compatibility report.
- Coverage of the real axes: small/fast vs larger, tool-calling vs not, plus vision.
- Fix the engine-side issues the sweep surfaces (Ollama preset, capability resolution, output-quirk tolerance) — measured before/after.
- A clear written report separating engine bugs from model-quality limits.

**Non-Goals:**
- Not trying to make every tiny model heal well — some will simply be too weak; the goal is that the *engine* never mis-handles a reachable model, and that capable small models reach their ceiling.
- No new runtime dependency or Ollama-specific client (use the OpenAI-compatible endpoint).
- The sweep is not added to PR CI (needs the lab host); it is reproducible on demand.
- No changes to the verification contract — a plausible-but-wrong heal must still fail verification.

## Decisions

### D1: Reuse the eval corpus as the primary sweep signal

The 60-fixture replay corpus (`heal.evals`) grades element-identity offline — no browser, no external sites, deterministic page content — so it isolates *model* behaviour from environment flakiness and runs fast enough to sweep ~10 models. The sweep runner iterates a model list, building `HealSettings(model=…, base_url=…, api_key="ollama")` per model, and records doctor capabilities + per-fixture heal outcome. A small live-browser smoke set (the bundled `heal_locator_drift` page) confirms the full listener path on 2–3 representative models, but the corpus is the comparative metric.

*Alternative rejected*: live atests per model — too slow and conflates browser/page flakiness with model quality.

### D2: Curated model selection over all 18

Sweep a representative subset chosen for the capability axes, not every model (coding/duplicate models add noise):

| Bucket | Models |
|---|---|
| Tiny, no/weak tools | `llama3.2:latest` (3.2B), `phi3` (3.8B), `phi4-mini` (3.8B), `gemma3` (4.3B) |
| 8B, tool-capable | `llama3.1` (8B), `qwen3:8b`, `granite3.2:8b` |
| Larger small | `gemma3:12b`, `qwen3:14b` |
| Vision | `llama3.2-vision` (form/assertion screenshot path) |

The runner takes the list as config so it can be re-pointed at any Ollama host or expanded.

### D3: Ollama backend preset and doctor-driven capability

Add an `ollama` `BackendPreset` (URL marker `:11434` or `/v1` on a LAN host is ambiguous, so detect by an explicit `ollama` hint or the `11434` port): default `tools=unreliable`, `structured_output=prompted` (the safe floor), `vision` per model. Because Ollama tool support is per-model, the **`heal doctor` probe is authoritative** — `override_capabilities(role, probed)` already exists; the sweep (and a `HEAL_DOCTOR_ON_START`-style opt-in, if warranted) uses it so a tool-capable model isn't needlessly pinned to prompted. Strip Ollama-unsupported request parameters via the model profile / `prepare_tools` as needed (mirrors the vLLM strict-strip).

*Alternative rejected*: assume all Ollama models are prompted-only — wastes the capability of `llama3.1`/`qwen3`; the probe already tells the truth cheaply.

### D4: Output-quirk tolerance in the prompted path

Small models commonly wrap JSON in `<think>…</think>`, markdown fences, or trailing prose. pydantic-ai's prompted output handles much of this, but the sweep will reveal gaps. Any tolerance added (e.g. extracting the JSON object from noise before validation) must be a *pre-parse normalisation*, never a relaxation of the schema or the live verification — a malformed-but-parseable wrong locator still has to fail `verify_candidate`. Fixes here are driven by observed failures, not speculation.

### D5: Report format

`experiments/ollama-small-models/FINDINGS.md`: the per-model matrix (reachable, doctor caps, resolved output mode, corpus accuracy %, median latency, median tokens, notable failure modes) plus a written **Issues** section classifying each finding as engine-bug (fix here), model-limit (document), or config-gotcha (document). A machine-readable `results.json` from the runner backs the matrix. Before/after rows for any fix made.

## Risks / Trade-offs

- [Model quality vs engine bug confusion] → the report classifies every issue; verification-in-validators guarantees a wrong heal can't pass, so "healed wrong element" is impossible by construction — failures are "didn't heal" or "engine error", which are distinguishable.
- [Lab host dependency / reproducibility] → runner is host-configurable (`OLLAMA_HOST` / CLI arg) and skips cleanly when unreachable; results.json + FINDINGS are committed so the report stands without the host.
- [Sweep latency on a busy local box] → corpus-first keeps it bounded; per-model timeouts and a model subset keep total runtime reasonable; long runs go to the background.
- [Over-fitting fixes to one Ollama version] → fixes target capability *resolution* and *parse tolerance* (general), not model-specific hacks; the vLLM/MiniMax presets are the precedent.

## Migration Plan

Additive. The Ollama preset and any parse tolerance are backward-compatible (existing backends unaffected; verification unchanged). Docs gain an Ollama how-to entry and the small-model matrix. No version-breaking changes.

## Open Questions

- Should `heal doctor` optionally run automatically at suite start to resolve per-model capability (an opt-in `HEAL_PROBE_ON_START`)? Decide from sweep evidence — valuable if presets prove too coarse for Ollama's per-model variance.
- Whether any small model is good enough to recommend as a default self-hosted option in the docs, or whether the honest message stays "probe yours with `heal doctor`."
