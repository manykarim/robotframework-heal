# Proposal: tiered-healing-and-frames

## Why

Exploration experiments (2026-06-11, `experiments/dom-edge-cases/`, `experiments/selection-mode/`) settled four facts about the current engine:

1. **iframes cause false heals** — the engine "healed" a broken locator to `css=iframe#content-frame`, clicking the iframe element itself; the rerun "passed" and the real failure moved downstream. Frame content is invisible in DOM evidence, nothing excludes iframes as interaction targets, and proposals never use Playwright's frame-piercing syntax (which the probe confirmed works unchanged through `get_element_count`/`get_element_states`).
2. **Selection mode beats generation mode for every model** on 53 real recorded heals: −68% prompt size, +5 accuracy points on capable models (89%→94%), **+27 points on llama-3.1-8B (60%→87%)**. Deterministic candidates covered the truth element in 52/53 cases.
3. **A zero-LLM fuzzy tier solves 85% of real cases in ~7ms** — but produced 1/53 plausible-but-wrong picks that live verification cannot catch, so it must not act on confidence alone.
4. The keyword's own timeout before failure (3–5s) often exceeds the heal itself; greedy reuse removes it within a run but not across runs.

Separately, SeleniumLibrary remains the most-requested compatibility gap (the sibling project supports it; our `SessionDriver` protocol was designed to make it cheap).

## What Changes

- **Frame-aware healing**: per-frame DOM serialization tagged with the frame's pierce prefix in evidence; locator agent may propose `frame >>> inner` selectors (validator verifies them unchanged via `count`); `iframe`/`frame` tags are blocklisted as interaction targets — the blocklist alone fixes the false heal and lands first.
- **Tiered locator selection** replacing the single generation path: Tier 1 deterministic candidates + fuzzy ranking (0 tokens), Tier 2 LLM index-pick over top-K candidates with element info (~100 tokens, flat schema), Tier 3 generation mode with full DOM (today's path, fallback only). Per the false-heal lesson, Tier 1 never auto-applies without Tier 2's judgment; all tiers feed the existing live verification.
- **Cross-run heal memory**: greedy `fixed_locators` warm-started from `history.sqlite` at run start (verify-before-swap already guards staleness); persists the keyword-timeout savings across runs.
- **SeleniumLibrary driver**: third `SessionDriver` implementation (query/inspect/act incl. dismiss candidates and form analysis), registered with the listener; locator syntax mapping for proposals.
- **Eval-corpus harvesting**: `heal corpus` collects ground-truth cases (recorded heals with verified locators) from run stores into the replay-eval fixture set, so every run grows the quality benchmark that made this exploration possible.

## Capabilities

### New Capabilities

- `frame-healing`: frame enumeration and per-frame evidence, frame-pierced proposals/verification, interaction-target blocklist.
- `tiered-locator-selection`: the tiered candidate pipeline (deterministic rank → LLM selection → generation fallback) with its safety rules.
- `heal-memory`: cross-run warm start of known fixes with verify-before-swap staleness guards.
- `selenium-driver`: SessionDriver implementation for SeleniumLibrary.
- `eval-corpus`: harvesting ground-truth fixtures from run stores into the eval set.

### Modified Capabilities

None — the prior change's specs are not yet archived into `openspec/specs/`; the tiered pipeline is specified as a new capability layered onto `locator-healing` (its verification requirements remain in force).

## Impact

- **Code**: `heal/drivers/browser.py` (frame serialization/enumeration, blocklist support), `heal/drivers/selenium.py` (new), `heal/drivers/dom.py` (candidate info extraction), `heal/core/agents/locator.py` (selection agent + tier orchestration in the locator plugin), `heal/rf/listener.py` (warm start, Selenium registration), `heal/cli/main.py` (`corpus` command), `heal/evals/`.
- **Dependencies**: + `robotframework-seleniumlibrary` (likely optional extra); no removals.
- **Users**: no breaking changes; new settings (`HEAL_LOCATOR_TIERS`, `HEAL_WARM_START`) default to the new behavior with opt-outs; token costs drop substantially (median heal ~1.7k → ~hundreds of tokens).
- **Risk**: plausible-but-wrong selections (proven failure class) → Tier 2 judgment mandatory above Tier 1, eval-corpus regression runs per tier change; frame evidence size on frame-heavy pages → bounded per-frame budgets, experiment-gated.
