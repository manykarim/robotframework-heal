# Tasks: tiered-healing-and-frames

Experiment-gated as before: **[EXPERIMENT]** tasks record findings in the relevant `experiments/*/FINDINGS.md` before dependents are built. Evidence base for this change: `experiments/dom-edge-cases/`, `experiments/selection-mode/`.

## 1. Frame safety and frame-aware healing

- [ ] 1.1 Interaction-target blocklist (`iframe`/`frame`/`html`/`body`/`head`) in the locator validator and deterministic candidate generation, with explanatory rejection feedback; regression test reproducing the recorded false heal (edge-case page)
- [ ] 1.2 **[EXPERIMENT]** Frame-evidence sizing: measure per-frame serialization on a frame-heavy page (multiple/nested/cross-origin frames); settle filter defaults (visibility, same-origin, min size) and per-frame share of `MAX_DOM_CHARS`; record in `experiments/dom-edge-cases/FINDINGS.md`
- [ ] 1.3 `BrowserDriver` frame enumeration + tagged per-frame DOM sections in `get_page_source`/`get_simplified_dom` (cross-origin noted, budgets per 1.2); unit tests with fake browser
- [ ] 1.4 Locator prompt teaches the `frame >>> inner` prefix convention from the evidence tags; atest: `edge_cases.robot` iframe test heals correctly (button inside the frame, not the frame)

## 2. Tiered locator selection

- [ ] 2.1 Candidate info extraction in `heal.drivers.dom` (per-candidate tag/text/attrs from the recorded DOM) and fuzzy ranking helper (`thefuzz`, normalized failed-locator tokens) with unit tests
- [ ] 2.2 Selection agent (`{index, reason}` flat schema) with index→locator mapping in the output validator reusing the existing live verification + per-candidate retry feedback
- [ ] 2.3 Tier orchestration in `LocatorDriftPlugin.heal`: rank → select(top-K) → fallback to generation on no-candidates/miss/exhaustion; `HEAL_LOCATOR_TIERS` setting (default `selection`); unit tests for every tier transition incl. forced generator-miss
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
