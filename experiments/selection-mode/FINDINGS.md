# Findings: tiered locator selection (tokens, small models, speed)

**Date**: 2026-06-11 · 53 unique ground-truth cases mined from real run stores
(verified healed locators across sauce/car/todo/insurance/ait apps) · `probe.py`, `no_llm_floor.py`

## Selection mode vs generation mode (probe.py)

GEN = current behavior (simplified DOM in prompt, model writes CSS).
SEL = deterministic candidates (`dom.generate_proposals`) + element info, model returns an index.

| Model | GEN acc | SEL acc | avg prompt | avg latency |
|---|---|---|---|---|
| gpt-4.1-nano | 89% | **94%** | 4799 → **1520 chars (−68%)** | 1.6s → 1.6s |
| gemini-2.5-flash-lite | 89% | **94%** | −68% | 1.3s → 0.9s |
| llama-3.1-8b-instruct | 60% (+1 err) | **87%** | −68% | 2.4s → 1.3s |

1. **Selection mode is more accurate for every model**, including capable ones (+5pts).
2. **It rescues small models**: llama-8b +27 points (60%→87%) — picking an index is
   categorically easier than generating valid unique CSS.
3. **−68% prompt size** (and output shrinks from selectors to one integer).
4. Generator coverage: the truth element was among the deterministic candidates in
   **52/53 cases** — generation mode remains needed only as a fallback tier.

## Zero-LLM floor (no_llm_floor.py)

Deterministic candidates + thefuzz ranking against the failed locator's tokens,
"confident" = score ≥75 with margin ≥15:

- **45/53 (85%) solved with zero LLM calls, median 7ms** (max 172ms)
- 7/53 ambiguous → escalate to LLM selection
- **1/53 wrong-confident** — `id=last_name` matched `input#firstname` over `#surname`.
  Critically, live verification CANNOT catch this class (the wrong field is unique,
  visible, type-compatible, and the fill succeeds) — a false heal.

**Consequence**: the zero-LLM tier must not auto-apply on fuzzy confidence alone.
Either a stricter threshold (cost: more escalations) or a tiny LLM confirmation
over the top-3 candidates (~300 chars — still a ~90% token cut) keeps judgment
in the loop. Same false-heal risk class as the iframe finding: "verified" is
necessary but not sufficient when the wrong element is itself plausible.

## Latency context (from 168 recorded events)

- 97% of heals are single-round; median 2.7s on nano; multi-round adds ~1.6s/round
- tokens scale ~chars/3 with DOM size; latency is flat for fast models →
  token reduction is a **cost/small-model lever**, a latency lever only for slow
  reasoning backends (MiniMax-class, ~15s)
- the keyword's own timeout (3–5s) before failure often exceeds the heal itself;
  greedy reuse already removes it for repeats → warm-starting `fixed_locators`
  from `history.sqlite` would remove it across runs
