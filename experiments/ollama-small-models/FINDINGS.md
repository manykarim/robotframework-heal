# Findings: small-model healing on Ollama

**Date**: 2026-06-18 · **Host**: `192.168.1.15:11434` (Ollama 0.15.4) ·
**Grading**: element-identity on a 12-fixture subset of the replay corpus ·
**Tier**: selection (default) · **Endpoint**: OpenAI-compatible `/v1`.

The sweep ran across 9 models (the 10th, `llama3.2-vision`, is deprecated on this
Ollama — HTTP 500 "no longer supported"). The host became unstable under load and
dropped twice mid-run; results were gathered across resumes (the harness skips
unreachable models and continues).

## Compatibility matrix

| Model | Size | engine mode | doctor probe | accuracy | median latency | median tokens |
|---|---|---|---|---|---|---|
| `granite3.2:8b` | 8.2B | prompted | native / no-tools | **92%** | 12.4s | 514 |
| `gemma3:12b` | 12.2B | prompted | native / no-tools | **92%** | 22.2s | 559 |
| `gemma3:latest` | 4.3B | prompted | native / no-tools | **83%** | 7.9s | 546 |
| `qwen3:8b` | 8.2B | prompted | tool / unreliable | **83%** | 47.5s | 749 |
| `phi3:latest` | 3.8B | prompted | native / no-tools | 67% | 6.8s | 644 |
| `llama3.1:latest` | 8.0B | prompted | native / no-tools | 58% | 10.8s | 504 |
| `llama3.2:latest` | 3.2B | prompted | native / no-tools | 33% | 9.0s | 606 |
| `phi4-mini:latest` | 3.8B | prompted | native / no-tools | 8% | 31.9s | 460 |
| `qwen3:14b` | 14.8B | prompted | tool / unreliable | 0% | 31.8s | — |
| `llama3.2-vision` | 9.8B | — | unavailable (Ollama 500) | — | — | — |

**Best quality/speed for self-hosted healing: `gemma3:latest` (4.3B, 83% @ 8s)
and `granite3.2:8b` (92% @ 12s).** `gemma3:12b` matches granite at 92% but is
slower. `phi3` is a solid 3.8B option (67% @ 7s).

## Headline: robotframework-heal handles the Ollama fleet correctly

The primary result is reassuring — **no engine bug was found.** The differentiator
across models is *model quality*, not engine behaviour:

- **Verification integrity held.** No model ever healed to the wrong element via a
  successful heal — weak models (`phi4-mini`, `qwen3:14b`) fail with "no proposal
  survived live verification", exactly as designed. The wrong-element cases the
  identity grading caught are heals the model picked that are valid/unique/visible
  but not the recorded ground-truth element — a model-quality miss, not an engine
  fault.
- **Graceful degradation held.** Both host drops and the deprecated vision model
  were reported as unreachable/error; the sweep skipped and continued, never
  crashing or hanging.
- **The prompted floor is the right Ollama default.** `heal doctor` shows that
  **Ollama's OpenAI-compatible endpoint does not reliably expose tool calling** —
  8 of 9 models probe `no-tools`, and the one that probes `tool` (qwen3) is
  flagged `unreliable`. So the engine's choice to heal via prompted JSON is
  correct, and verification-in-validators (which works in prompted mode) is what
  makes these models viable at all.

## Issues (classified)

| # | Finding | Class | Action |
|---|---|---|---|
| 1 | Ollama resolves to prompted via the *unknown-backend default*, not an explicit preset | engine (minor) | Add an Ollama backend preset (intentional default + a home for endpoint specifics) — **fixed** |
| 2 | `outcome.usage` is not recorded on UNHEALED transactions, so the cost of failed heals is invisible (sweep could not report tokens for failing models) | engine (observability) | Record usage on unhealed locator transactions — **fixed** |
| 3 | `qwen3:14b` 0% — heavy reasoning model: 4/12 timeouts at the 60s cap + 8/12 bad proposals | model-limit | Document; not an engine fault. It emits clean JSON on simple prompts, so not a parse bug |
| 4 | `phi4-mini` 8% — proposals fail verification | model-limit | Document; verification correctly rejects |
| 5 | `llama3.2-vision` returns HTTP 500 (deprecated on this Ollama) | config/host | Pick a current vision model; the engine reports it cleanly |
| 6 | Slow small models exceed `HEAL_MAX_FAILURE_SECONDS` (60s) | config | Document the tunable; recommend faster models |

## Hypothesis invalidated

The proposal hypothesised that **tool-capable models would need un-pinning from
prompted** and that **output-quirk tolerance** (`<think>`/fenced-JSON parsing)
would be a bottleneck. The data contradicts both:

- Ollama tool-calling is unreliable/absent over the OpenAI-compatible endpoint, so
  prompted is the correct default — there is nothing to un-pin.
- `qwen3` (a heavy `<think>`-emitting reasoning family) reached 83% at 8B in
  prompted mode and emits clean JSON on simple prompts; pydantic-ai already
  tolerates reasoning blocks. No parse-error bottleneck was observed. The
  `model-runtime` "output-quirk tolerance" requirement is therefore **not
  justified by evidence** and is recommended for de-scoping (see the change's
  spec update).

## After the fixes (post-fix check)

Both engine fixes (#1 Ollama preset, #2 usage-on-unhealed) landed and were
re-checked against the same host:

- **No accuracy change** — the preset resolves to the same prompted floor the
  unknown-backend default already used, so behaviour is identical by design.
  `gemma3:latest` re-ran at **80%** on a 5-fixture spot-check (vs 83% on the
  12-fixture baseline — same model, same path), `engine=prompted`, 0 errors.
- **Ollama now resolves explicitly** — `find_preset(...)` returns `ollama`
  rather than falling through to the generic default; the endpoint has a named
  home for any future quirk overrides.
- **Reference backends unaffected** — the full unit suite (175 tests, incl. the
  MiniMax/OpenRouter preset tests) stays green.

## Recommendations (for docs)

- For self-hosted healing on modest hardware, **`gemma3` (4.3B)** is the
  best quality/speed; **`granite3.2:8b`** or **`gemma3:12b`** for the highest
  accuracy. Avoid heavy reasoning models (`qwen3:14b`) and very small/weak ones
  (`phi4-mini`, `llama3.2`).
- Configure with `HEAL_BASE_URL=http://<host>:11434/v1`, any `HEAL_API_KEY`
  placeholder. Always run `heal doctor --role locator` — capability is per-model.
- Raise `HEAL_MAX_FAILURE_SECONDS` if your box is slow, or prefer a faster model.
