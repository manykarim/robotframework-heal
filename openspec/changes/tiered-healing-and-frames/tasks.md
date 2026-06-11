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
- [ ] 2.4 Run the eval corpus per tier mode against both reference backends; record accuracy/token deltas in `experiments/selection-mode/FINDINGS.md`; corpus accuracy must not regress vs generation mode

## 3. Heal memory (cross-run warm start)

- [ ] 3.1 History query for recent healed mappings (per source file, bounded age/count) + listener warm start under `HEAL_WARM_START` (default true)
- [ ] 3.2 Warm-start provenance: applied swaps recorded as events marked reused-from-history; dashboard shows origin; staleness fall-through unit tests
- [ ] 3.3 atest: two consecutive runs — second run heals proactively with zero LLM requests (assert via summary.json token count)

## 4. SeleniumLibrary driver

- [ ] 4.1 **[EXPERIMENT]** Selenium primitive probe (`experiments/selenium-probe/`): count/visibility/innerText/readyState/scroll/screenshot/fill via SeleniumLibrary on the existing demo pages; confirm locator prefix mapping (`css:`/`xpath:`); record findings
- [ ] 4.2 Implement `heal/drivers/selenium.py` per probe findings (query/inspect/act, dismiss candidates, form issues, JS shadow-DOM serialization best-effort); protocol conformance tests with a fake webdriver
- [ ] 4.3 Register with the listener; optional-dependency packaging (`robotframework-heal[selenium]`, graceful absence); frame-target failures produce the frame-limitation RCA
- [ ] 4.4 atest: seeded locator-drift + timing suites running the shared demo pages under SeleniumLibrary (live-llm tag for drift)

## 5. Eval corpus

- [ ] 5.1 `heal corpus harvest <paths>` extracting deduplicated ground-truth fixtures (mining logic from the exploration probe) into `tests/evals/fixtures/`; idempotency test
- [ ] 5.2 Eval runner discovers fixtures dynamically; per-tier-mode reporting; harvest the existing `results/` stores as the initial corpus (~50 cases)
- [ ] 5.3 Docs: README/features updates (tiers, frames, Selenium, corpus), config reference additions, CHANGELOG entry
