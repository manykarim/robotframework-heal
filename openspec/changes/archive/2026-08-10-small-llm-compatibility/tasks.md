# Tasks: small-llm-compatibility

Experiments-first: the sweep (phase 2) runs before fixes (phase 3); fixes are driven by recorded findings, then re-measured (phase 4). Ollama host: `192.168.1.15:11434` (configurable).

## 1. Sweep harness

- [x] 1.1 Probed the host (18 models in inventory.json) and pinned the curated selection (models.py): 10 models across tiny/no-tools, 8B/tool-capable, larger-small, vision; 3 smoke models
- [x] 1.2 `sweep.py`: per-model doctor probe + corpus replay (element-identity grading), accuracy/latency/tokens/failure-modes, host-configurable, skips unreachable, writes results.json — smoke-validated
- [x] 1.3 `smoke.py`: live-browser heal of the bundled locator-drift suite for 3 representative models (full listener path through Ollama)

## 2. Run the sweep (baseline)

- [x] 2.1 **[EXPERIMENT]** Swept 9 models (vision deprecated on host); results.json captured (host dropped twice under load, resumed)
- [x] 2.2 FINDINGS.md: full matrix + issues classified. Headline: no engine bug — model quality is the differentiator; granite3.2:8b/gemma3:12b 92%, gemma3:4B 83%. Prompted floor validated (Ollama tool-calling unreliable)

## 3. Engine fixes (driven by findings)

- [x] 3.1 Ollama backend preset (`:11434` detection, prompted floor, tools unreliable) + unit tests; engine now resolves Ollama explicitly
- [x] 3.2 Probe-driven upgrade kept via existing `override_capabilities`; evidence shows Ollama tool-calling is unreliable so prompted is the correct default (no forced upgrade) — unit-tested
- [x] 3.3 De-scoped per evidence: pydantic-ai already tolerates `<think>`/reasoning; no parse bottleneck found (qwen3 83% @ 8B, clean JSON on simple prompts). Spec updated; no speculative code added
- [x] 3.4 Observability fix: record token usage on UNHEALED locator transactions (the sweep could not report cost of failed heals) + unit test

## 4. Re-measure and report

- [x] 4.1 Post-fix check: gemma3 80% via the explicit Ollama preset (consistent with baseline; no regression). Reference backends (MiniMax/OpenRouter) unaffected — 175 unit tests pass
- [x] 4.2 FINDINGS.md finalized: 9-model matrix, engine-correct headline, classified issues, invalidated hypotheses, before/after post-fix check + recommendations
- [x] 4.3 Docs: enriched Ollama setup in model-providers how-to + small-model compatibility matrix in the model-tiers explanation
