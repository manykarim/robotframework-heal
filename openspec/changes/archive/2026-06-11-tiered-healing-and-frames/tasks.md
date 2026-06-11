# Tasks: tiered-healing-and-frames

Experiment-gated as before: **[EXPERIMENT]** tasks record findings in the relevant `experiments/*/FINDINGS.md` before dependents are built. Evidence base for this change: `experiments/dom-edge-cases/`, `experiments/selection-mode/`.

## 1. Frame safety and frame-aware healing

- [x] 1.1 Interaction-target blocklist (`iframe`/`frame`/`html`/`body`/`head`) in the locator validator and deterministic candidate generation, with explanatory rejection feedback; regression test reproducing the recorded false heal (edge-case page)
- [x] 1.2 **[EXPERIMENT]** Frame-evidence sizing — DONE: ~0.15s/frame, two-level piercing works, cross-origin serializable via CDP (same-origin filter dropped); defaults: visible ∧ ≥20×20px, depth ≤2, ≤5 frames by area, per-frame cap MAX_DOM_CHARS/4
- [x] 1.3 `BrowserDriver` frame enumeration + tagged per-frame DOM sections in `get_simplified_dom` (main `get_page_source` semantics preserved for dialog/shadow paths); filters per 1.2; unit tests with fake browser
- [x] 1.4 Locator prompt teaches the `frame >>> inner` prefix convention; live atest green: iframe heal lands on the button inside the frame (`css=#content-frame >>> css=#frame-submit`), shadow/closed cases unchanged; suite promoted to tests/atest/heal/heal_dom_edge_cases.robot

## 2. Tiered locator selection

- [x] 2.1 Candidate info extraction in `heal.drivers.dom` (describe_candidates, candidate_tags_for) and fuzzy ranking helper (rank_candidates) with unit tests
- [x] 2.2 Selection agent (`{index, reason}` flat schema) with index→locator mapping in the output validator reusing the shared live verification (`verify_candidate`) + per-candidate retry feedback
- [x] 2.3 Tier orchestration in `LocatorDriftPlugin.heal`: rank → select(top-8) → generation fallback on no-candidates/exhaustion/rerun-failure; `HEAL_LOCATOR_TIERS` (default `selection`); tier-transition unit tests; live atest green (506 tokens)
- [x] 2.4 Corpus evals run (60 fixtures × 2 backends × 2 modes): selection = −65–70% tokens, equal accuracy on nano (92/92), −4pts on MiniMax (93 vs 97) — accepted and documented (strong-reasoning models extract more from full DOM); defaults stay selection with generation fallback/opt-out

## 3. Heal memory (cross-run warm start)

- [x] 3.1 History query (`recent_mappings`) + lazy listener warm start under `HEAL_WARM_START` (default true), scoped per source file
- [x] 3.2 Warm-start provenance: history-reused swaps recorded as events (`warm-N`, origin=history); staleness + scoping + disable unit tests
- [x] 3.3 Verified live: two consecutive runs with shared history — run 2 healed 2/2 proactively with 0 tokens (summary.json)

## 4. SeleniumLibrary driver

- [x] 4.1 **[EXPERIMENT]** Selenium primitive probe — all primitives confirmed (FINDINGS.md); caveats: `page_source` is a property, no shadow-piercing selectors, no frame piercing
- [x] 4.2 Implement `heal/drivers/selenium.py` (query/inspect/act, dismiss candidates, form issues, JS shadow serialization, locator translation); protocol conformance tests with fake webdriver
- [x] 4.3 Registered with the listener; `robotframework-heal[selenium]` extra; frame-limitation note in evidence/RCA
- [x] 4.4 atest green live: locator drift healed via selection tier + greedy reuse (2/2); timing healed with page_load_strategy=none ("waited 6.1s") — default blocking strategy absorbs document loads itself (recorded)

## 5. Eval corpus

- [x] 5.1 `heal corpus <paths>` harvesting deduplicated ground-truth fixtures into `tests/evals/fixtures/`; idempotency test + live idempotency verified
- [x] 5.2 Eval runner discovers fixtures dynamically with element-identity grading and tier-mode reporting; initial corpus harvested: 60 fixtures from existing runs
- [x] 5.3 Docs: README/features/config updates (tiers, frames, Selenium extra, warm start, corpus), CHANGELOG entry
