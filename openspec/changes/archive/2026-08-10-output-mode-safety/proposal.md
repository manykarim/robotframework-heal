# Proposal: output-mode-safety

## Why

Two gaps left by `small-llm-compatibility`, both established by measurement in
`experiments/small-model-sweep/FINDINGS.md` (9 models × 2 output modes × 20
fixtures stratified over 11 suites, on OpenRouter):

1. **A preset can pin an output mode the model cannot produce.** Presets resolve
   per *endpoint*, capability is per *model*. `qwen3-8b` behind a prompted-pinned
   preset scored **0%** (19 of 20 fixtures hit the 60s cap) against **95%**
   native. Its probe already said `prompted_output=FAIL, native_output=PASS`;
   nothing consulted it at runtime.

2. **A shipped requirement is factually wrong.** `model-compatibility-report`
   claims the report "can never record a plausible-but-wrong locator as a
   successful heal". Measured: **30 of 180** prompted cells did exactly that
   (10 of 20 for `llama-3.2-3b`). Verification checks uniqueness, visibility and
   rerun — none of which is semantic — so `Fill Text id=pass secret_sauce`
   healed into a visible username field and the test passed. Element-identity
   *grading* catches these, not verification.

## What Changes

- **Add an output-mode safety rule** to `model-runtime`: verify the resolved
  structured-output mode can actually be produced before healing with it, and
  fall back only when it demonstrably cannot. Deliberately narrow — a probe
  measures whether a transport *works*, not whether it *heals better*
  (`gemma-3-4b` passes both probes yet scores 75% prompted against 35% native;
  MiniMax probes tool-capable yet is pinned to prompted on separate evidence).
  A passing mode is therefore never second-guessed.
- **Correct the verification-integrity requirement** in
  `model-compatibility-report` to state what verification actually guarantees,
  and require that wrong-element heals be counted and reported rather than
  assumed impossible.

## Capabilities

### Modified Capabilities

- `model-runtime`: output-mode safety rule with probe-backed fallback.
- `model-compatibility-report`: accurate verification semantics; wrong-element
  heals reported as a first-class metric.

## Impact

- **Code**: implemented — `src/heal/core/doctor.py` (`safe_output_mode`,
  `probe_output_modes`), `src/heal/core/runtime.py`
  (`ensure_safe_output_mode`, `capability_notes`), `src/heal/core/engine.py`,
  `src/heal/core/settings.py` (`HEAL_PROBE_CAPABILITIES`),
  `src/heal/rf/listener.py`, `src/heal/cli/main.py`, `src/heal/evals/sweep.py`.
- **Config**: `HEAL_PROBE_CAPABILITIES` (default true). One tiny probe call per
  endpoint, cached for the run and shared across roles.
- **Risk**: a new default network call at first heal. Bounded by
  `HEAL_MAX_FAILURE_SECONDS`, run outside the per-failure budget, and failures
  leave the configured mode untouched. Disable with
  `HEAL_PROBE_CAPABILITIES=false`.
