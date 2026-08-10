# Tasks: output-mode-safety

Evidence-first: the sweep (`experiments/small-model-sweep`) established both
findings before any code was written, and the fix was re-measured against the
same fixtures afterwards.

## 1. Safety rule

- [x] 1.1 `safe_output_mode(working, preferred)` — keep a mode that passes, override only one that demonstrably fails; never rank two working modes
- [x] 1.2 `probe_output_modes(model, preferred)` — tests the intended mode first and stops when it works (one call in the common case), bounded by `HEAL_MAX_FAILURE_SECONDS`
- [x] 1.3 `AgentRuntime.ensure_safe_output_mode(role)` — cached per endpoint so roles sharing a model probe once; evicts agents cached under the corrected mode
- [x] 1.4 Engine hook placed outside the per-failure `wait_for` (a probe is not part of the failure budget), gated by `HEAL_PROBE_CAPABILITIES` (default true)
- [x] 1.5 Surfacing: `AgentRuntime.capability_notes`, RF listener warning, and `heal doctor` printing both `probed:` and `healing:`

## 2. Report accuracy

- [x] 2.1 Count wrong-element heals per cell (`wrong_element`) in the packaged sweep harness
- [x] 2.2 Record `effective_output` / `mode_corrected` so a runtime correction is visible in results rather than hidden behind the configured mode
- [x] 2.3 Correct the docs claim that verification prevents wrong-element heals (`docs/explanation/model-tiers.md`, `experiments/ollama-small-models/FINDINGS.md`)

## 3. Validation

- [x] 3.1 Corpus, mode still pinned to prompted: `qwen3-8b` 0% → 100%; `gemma-3-4b` 75→80%, `llama-3.1-8b` 60→50%, `granite-4.1-8b` 95→95% (all left alone, within the sample's 5% resolution)
- [x] 3.2 Live browser through the RF listener, 4 suites: `gpt-4.1-nano` 8/8; `qwen3-8b` rule on 8/8; rule off **0/2** (per-failure budget exceeded)
- [x] 3.3 Third backend via CI: all three MiniMax models probe tool-capable yet keep healing in prompted — the rule correctly declines to override a deliberate, evidence-backed preset
- [x] 3.4 16 unit tests covering the rule, probe short-circuit, per-endpoint caching, stale-agent eviction, and explicit-mode override
