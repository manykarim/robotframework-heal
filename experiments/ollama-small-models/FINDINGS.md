# Findings: small-model healing on Ollama (PARTIAL — host went down mid-sweep)

**Date**: 2026-06-18 · **Host**: `192.168.1.15:11434` (Ollama 0.15.4) · grading: element-identity on the 60-fixture replay corpus (12-fixture subset for this baseline) · selection tier (default).

> **Status: incomplete.** The Ollama host became unreachable after the first 3
> (smallest) models. Models from `gemma3` (4.3B) upward returned connection
> errors; a direct probe afterward confirmed the host was down
> (`Couldn't connect to server`). Most likely the box OOM'd or Ollama crashed
> while loading the larger models. Re-run the remaining 7 once the host is back
> (the harness skips reachable models, so `sweep.py --models <remaining>` resumes).

## Baseline matrix (3 models that completed)

| Model | Size | engine mode | doctor probe | accuracy | median latency | median tokens |
|---|---|---|---|---|---|---|
| `llama3.2:latest` | 3.2B | prompted | native / no-tools | 33% | 9.0s | 606 |
| `phi3:latest` | 3.8B | prompted | native / no-tools | **67%** | 6.8s | 644 |
| `phi4-mini:latest` | 3.8B | prompted | native / no-tools | 8% | 31.9s | 460 |

## Observations so far

1. **Engine→capability gap (engine-bug candidate).** For every Ollama model the
   engine resolves `engine=prompted` (the safe floor for an unknown backend),
   while the doctor probe reports `native` output works. None of these three
   tiny models tool-call (`doctor_tools=none`), so prompted is fine for them —
   but the gap matters for the tool-capable 8B models (llama3.1/qwen3/granite)
   that didn't get to run. **Fix target (phase 3):** an Ollama preset +
   probe-driven capability so a tool-capable Ollama model isn't pinned to
   prompted, and native is used where it's reliably faster.

2. **`phi4-mini` mostly fails verification** ("No locator proposal survived live
   verification" 7/12) and is slow (31.9s) — a **model-quality limit**, not an
   engine bug. Verification correctly rejects its bad proposals rather than
   healing wrong.

3. **`phi3` is the surprise** — 67% at 6.8s, the best small model so far.
   `llama3.2` is middling (33%); several of its misses are "healed a *different*
   valid element" (wrong-element, a model-quality miss the identity grading
   catches — verification can't, since the element is valid/unique/visible).

4. **Graceful degradation works (engine behaving correctly).** When the host
   died, the doctor probe reported the endpoint unreachable, the sweep recorded
   each model as failed and continued — no crash, no hang. The "unreachable →
   skip" contract held.

5. **Timeouts at the 60s cap** appear on `llama3.2` (2/12) and `phi4-mini`
   (3/12) — small models on a loaded local box can exceed the per-failure
   budget. Worth noting in docs; `HEAL_MAX_FAILURE_SECONDS` is tunable.

## Next (blocked on host)

- Bring the Ollama host back up; re-run the remaining 7 models
  (`gemma3`, `llama3.1`, `qwen3:8b`, `granite3.2:8b`, `gemma3:12b`, `qwen3:14b`,
  `llama3.2-vision`) — especially the tool-capable ones, which exercise the
  engine→capability gap above.
- Then implement phase-3 fixes (Ollama preset, probe-driven resolution, any
  output-quirk tolerance the failures justify) and re-measure.
