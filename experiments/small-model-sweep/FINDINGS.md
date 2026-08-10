# Findings: small-model healing across output modes (OpenRouter)

**Date**: 2026-08-10 · **Backend**: OpenRouter (`https://openrouter.ai/api/v1`) ·
**Grading**: element identity · **Tier**: selection (default) ·
**Sample**: 20 fixtures, stratified across **11 suites**, duplicate actions removed ·
**Cells**: 9 models × {prompted, native} = 18, all completed.

This sweep replaces the methodology of `experiments/ollama-small-models`, whose
sample drew 11 of 12 fixtures from one suite. It also adds the axis that sweep
never tested: **output mode**. Raw per-fixture records are in `results.json`, so
every aggregate below can be recomputed without re-running.

The Ollama host was unavailable, so these are OpenRouter-served weights of the
same model *families* — different quantisation and serving stack. Model-to-model
comparison with the Ollama matrix is indicative, not exact (see `models.py`).

## Matrix

| Model | prompted | native | Δ | tokens (p→n) | latency (p→n) |
|---|---|---|---|---|---|
| `ibm-granite/granite-4.1-8b` | **95%** | **95%** | 0 | 513 → 339 | 1.0s → 0.4s |
| `openai/gpt-4.1-nano` *(reference)* | **95%** | **95%** | 0 | 485 → 409 | 1.6s → 2.0s |
| `qwen/qwen3-14b` | **95%** | **95%** | 0 | 752 → 690 | 12.5s → 7.8s |
| `google/gemma-3-12b-it` | 90% | 90% | 0 | 510 → 381 | 2.5s → 1.1s |
| `microsoft/phi-4` | 85% | 85% | 0 | 472 → 388 | 1.1s → 0.8s |
| `meta-llama/llama-3.1-8b-instruct` | 60% | **90%** | **+30** | 519 → 347 | 1.3s → 0.4s |
| `google/gemma-3-4b-it` | **75%** | 35% | **−40** | 520 → 339 | 2.5s → 1.2s |
| `qwen/qwen3-8b` | **0%** | **95%** | **+95** | — → 692 | — → 4.8s |
| `meta-llama/llama-3.2-3b-instruct` | 35% | 50% | +15 | 495 → 396 | 0.7s → 0.9s |

Aggregate: **native 81.1% mean accuracy at 442 median tokens; prompted 70.0% at
533**. Native is cheaper in 9 of 9 cells and faster in 8 of 9.

## 1. The prompted "universal floor" is not universal

`qwen/qwen3-8b` scored **0% in prompted mode — 19 of 20 fixtures hit the 60s cap
with zero tokens recorded** — and **95% in native mode**. It is a reasoning
model: in prompted mode it never emits parseable JSON inside the time budget.

The engine had the information to avoid this. The doctor probe for that model
reports:

```
tool_output=FAIL  native_output=PASS  prompted_output=FAIL  exploration_tool=FAIL
```

The probe says prompted is broken and native works. The `openrouter` preset pins
prompted anyway, because presets are resolved per *backend* and the probe is
never consulted during a run (`override_capabilities` has no production caller).
This is the same design the `ollama` preset copies.

**This is a genuine engine defect, not a model limitation** — the difference
between a 95% model and a 0% model is a default the engine chose against its own
evidence.

## 2. …but native is not a safe universal default either

`google/gemma-3-4b-it` moves the other way: **75% prompted → 35% native**. Its
native-mode failures are proposal quality, not transport — "no locator proposal
survived live verification" 11 times out of 20, versus once in prompted mode.
Schema-constrained decoding appears to cost a 4B model more than the freer
prompted form gains it.

Critically, **the doctor probe cannot predict this**: gemma-3-4b passes both
`prompted_output` and `native_output`. The probe measures whether a transport
*works*, not whether it *heals better*.

So the defensible rule from this data is narrow, and it is a safety rule rather
than a ranking rule:

> Never resolve to an output mode the probe reports as FAILING when another mode
> passes. Where both pass, the probe cannot choose — that needs measurement.

Applied here, that rule fixes `qwen3-8b` (0% → 95%) and leaves `gemma-3-4b`
untouched at 75%.

## 3. Wrong-element heals are the dominant weak-model failure — and they pass verification

**30 of 180 prompted cells and 23 of 180 native cells healed to the wrong
element and were reported as successful heals.** For `llama-3.2-3b` it is **10 of
20** — half its fixtures.

These are not near-misses. Actual examples, all of which resolved uniquely, were
visible, and reran the keyword successfully:

| Keyword | Ground truth | Healed to |
|---|---|---|
| `Fill Text  id=pass  secret_sauce` | `#password` | `input#user-name` |
| `Fill Text  id=user  standard_user` | `#user-name` | `input#password` |
| `Fill Text  Password  password` | `input#input_password` | `input#input_username` |
| `Select Options By  Fuel Type  Petrol` | `select#fuel` | `select#make` |
| `Fill Text  Annual Mileage  10000` | `input#annualmileage` | `input#listprice` |

The first row types a secret into a visible username field. The test then
**passes**.

This refutes the claim carried in the Ollama report and promoted into the docs —
"No model ever healed to the *wrong* element via a successful heal … verification
integrity holds all the way down." Live verification checks that a locator
resolves uniquely, is visible, and lets the keyword rerun. **None of those
properties is semantic.** A locator can satisfy all three and still be the wrong
field.

The corpus proved this independently before the sweep: fixture
`ait-llm-4bdcdc82db6f7d1d` recorded `input#firstname` as ground truth for
`Fill Text id=last_name`, because an earlier heal picked the first-name field and
passed verification. It has been removed, and `heal corpus` now rejects
contradicting ground truth.

**Implication:** accuracy alone understates risk. A model at 35% accuracy with 10
wrong-element heals is more dangerous than one at 35% that simply refuses,
because the failures are silent. `wrong_element` is now recorded per cell.

## 4. Sampling changed the answer

On the old first-N sample (11 of 12 fixtures from one suite) the Ollama fleet
clustered at 83–92%. On 20 fixtures across 11 suites the same families spread
across 35–95%, and the mode sensitivity in §1–2 only appears at all because the
sample includes suites with several similar fields on one page — exactly the
cases where a wrong-element heal is possible.

## Validation of the fix

§1 was addressed by a **doctor-probe safety rule** in the engine: before healing,
verify the resolved output mode can actually be produced, and fall back only when
it demonstrably cannot (`HEAL_PROBE_CAPABILITIES`, default on). Re-running the
same 20 fixtures with the mode still pinned to prompted
(`validation-safety-rule.json`):

| Model | prompted, before | with safety rule | rule action |
|---|---|---|---|
| `qwen/qwen3-8b` | **0%** | **100%** | corrected → native |
| `google/gemma-3-4b-it` | 75% | 80% | left alone |
| `meta-llama/llama-3.1-8b-instruct` | 60% | 50% | left alone |
| `ibm-granite/granite-4.1-8b` | 95% | 95% | left alone |

The corrected cell's fingerprint confirms the mechanism rather than luck: 685
median tokens and 4.5s match the *native* baseline (692 / 4.8s), not prompted.
Cells the rule left alone move by at most 2 fixtures — the sample's resolution.

**End-to-end, real browser, through the Robot Framework listener** (4 live
suites: locator drift, keyword-arg, DOM edge cases incl. shadow DOM, Selenium):

| Configuration | Result |
|---|---|
| `gpt-4.1-nano` (control) | 8/8 passed |
| `qwen3-8b`, rule **on** | 8/8 passed, with `[WARN] heal: locator: 'prompted' output failed its probe on 'qwen/qwen3-8b'; using 'native' instead` |
| `qwen3-8b`, rule **off** (`HEAL_PROBE_CAPABILITIES=false`) | **0/2 passed** — "Healing transaction exceeded the per-failure time budget" |

The correction is never silent: it is logged as a warning per run and recorded in
`capability_notes`, and sweeps record `effective_output` / `mode_corrected`
alongside the configured mode.

## Recommendations

| Use | Model | Mode |
|---|---|---|
| Best overall | `ibm-granite/granite-4.1-8b` | native (95%, 339 tok, 0.4s) |
| Best if latency-insensitive | `qwen/qwen3-14b` | native (95%, 7.8s) |
| Solid mid-tier | `google/gemma-3-12b-it` | either (90%) |
| Needs native | `qwen/qwen3-8b` | handled automatically by the safety rule |
| **Requires** prompted | `google/gemma-3-4b-it` | prompted — native scores 35%, and both probes pass so the rule cannot tell |
| Avoid | `meta-llama/llama-3.2-3b-instruct` | 10/20 wrong-element heals |

The safety rule handles a *broken* mode. It cannot handle a mode that works but
heals worse — `gemma-3-4b` passes both probes, so pin it yourself with
`HEAL_OUTPUT_MODE` / `HEAL_LOCATOR_OUTPUT_MODE`.

## Open questions this sweep does not answer

- **Only locator drift was measured.** Triage never runs (the deterministic
  detector short-circuits it), vision was not probed, fix synthesis is not graded.
- **One backend.** Whether the mode sensitivity is a property of the weights or
  of OpenRouter's serving stack is untested; the Ollama host was unavailable.
- **20 fixtures** gives 5% resolution. Differences under ~10 points are noise.
- **Wrong-element rates are an upper bound** on true error: a few cases are
  ancestor/descendant mismatches (e.g. the cart container versus the badge span
  inside it) where the heal is arguably defensible.
