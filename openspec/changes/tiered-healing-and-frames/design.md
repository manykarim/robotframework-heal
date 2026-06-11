# Design: tiered-healing-and-frames

## Context

The agentic-heal engine (change `agentic-heal-rewrite`, complete) heals via a single generation path: simplified DOM → locator agent writes CSS → output validator verifies live → rerun. Exploration experiments against 53 real recorded heals and live edge-case pages established the evidence base for this change (full data: `experiments/dom-edge-cases/FINDINGS.md`, `experiments/selection-mode/FINDINGS.md`):

- iframe content is invisible to evidence and an iframe element itself passes verification → demonstrated **false heal**.
- Frame piercing (`frame >>> inner`) already works through the existing driver primitives — no engine change needed.
- Selection over deterministic candidates beats generation for every model tested (94% vs 89% on nano/flash-lite; **87% vs 60% on llama-3.1-8B**) at −68% prompt size; deterministic candidates contained the truth element in 52/53 cases; a fuzzy-rank tier alone solves 85% in ~7ms but produced 1/53 plausible-but-wrong picks that live verification cannot catch.

Constraints carried over: schema austerity (8B-class models), verification in output validators, driver calls marshalled to the RF main thread, budgets per transaction.

## Goals / Non-Goals

**Goals:**
- Eliminate the iframe false-heal class; heal locators whose targets live inside (same-origin) iframes.
- Cut locator-heal token cost by an order of magnitude for the common case while *increasing* accuracy, especially on small models.
- Carry known fixes across runs (remove repeat keyword-timeout + LLM cost on the next run).
- SeleniumLibrary parity for locator healing, timing, viewport, overlay and form diagnosis.
- Make the eval corpus self-growing.

**Non-Goals:**
- Cross-origin iframe content (platform-restricted; RCA-only like closed shadow roots).
- Healing frame *locators* themselves (only elements inside frames).
- Replacing live verification — every tier still verifies against the session.
- Selenium support in the MCP attached mode (post-run flows only need the store).

## Decisions

### D1: Interaction-target blocklist before anything else

`iframe`, `frame`, `html`, `body`, `head` are never valid heal targets for interaction keywords. Enforced in the locator validator (reject with explanatory feedback) and in deterministic candidate generation. This one rule fixes the demonstrated false heal independently of frame support and ships first.

### D2: Frames become tagged evidence, not a new pipeline

`BrowserDriver.get_page_source()` gains frame awareness: enumerate `iframe`/`frame` elements in the main DOM, serialize each frame's DOM via `evaluate_javascript("<frame-selector> >>> css=html", outerHTML)`, and append to the evidence as clearly delimited sections:

```
<main dom…>
<!-- FRAME id=content-frame : selectors inside must be prefixed "id=content-frame >>> " -->
<frame dom…>
```

The locator prompt explains the prefix convention; proposals arrive as `frame >>> inner` strings; `count`/`get_element_states`/`click` pierce natively (probe-confirmed) so **validator, plugins and rerun are unchanged**. Budgets: per-frame DOM capped (share of `MAX_DOM_CHARS`), frames filtered to visible, same-origin, ≥ minimum size; deeper nesting than one level is out of scope until evidence demands it.

*Alternative rejected*: a frame-scoped sub-transaction model (switch context into frame, heal there) — more invasive, breaks the "one evidence bundle per failure" model, and unnecessary given native piercing.

### D3: Tiered locator selection inside the existing plugin

The `LocatorDriftPlugin.heal` flow becomes a code-orchestrated ladder (no new agents-calling-agents):

```
candidates = generate_proposals(dom, keyword_tags)        # 0 tokens, ~7ms
ranked     = fuzzy_rank(candidates, failed_locator)       # thefuzz, element info
if ranked strong:                                          # Tier 2 (DEFAULT)
    pick = selection_agent(top_K candidates + info)        # index, flat schema, ~100 tok
    verify(pick) → rerun
if no candidates / no verified pick / generator missed:    # Tier 3 (fallback)
    generation_agent(full DOM)                             # today's path, unchanged
```

- **Tier 1 never auto-applies**: the 1/53 wrong-confident case (`firstname` vs `surname`) passes all live checks; fuzzy confidence is a *ranking* signal, not a decision. The cheap Tier 2 confirmation (~300–1500 chars) keeps semantic judgment in the loop at ~10% of generation cost.
- Selection agent schema: `{index: int, reason: str}` — flat, 8B-friendly (87% on llama-8B vs 60% generation).
- The selection output validator maps index → locator and runs the SAME live verification (count/visible/type/options) as today; rejected picks retry with per-candidate feedback; exhaustion falls through to Tier 3.
- `HEAL_LOCATOR_TIERS=selection` (default) | `generation` (old behavior) | `auto` reserved.

*Alternative rejected*: zero-LLM auto-apply above a stricter fuzzy threshold — saves ~1s and ~100 tokens per heal but reintroduces the unguarded false-heal class; the eval corpus can revisit this with more data.

### D4: Cross-run heal memory via the existing history DB

At listener start (lazy, first qualifying failure), load recent healed mappings (`failed_locator → healed_locator`, scoped per source file, last N days) from `history.sqlite` into `fixed_locators`. The existing greedy-swap guard (`count(broken)==0 and count(healed)>0` at use time, skip-parent rules) already provides verify-before-swap staleness protection; a swap that no longer verifies simply falls through to normal healing. Setting: `HEAL_WARM_START` (default true).

### D5: SeleniumDriver as the third SessionDriver

Wraps the SeleniumLibrary instance (`driver` property): `find_elements` for count/visibility, `execute_script` for readyState/viewport/innerText/scroll, `get_page_source` (Selenium pierces nothing — open shadow DOM support is best-effort via JS serialization like Browser), screenshot via webdriver PNG, dismiss candidates from `<dialog open>`/common banner heuristics, `fill_text` via clear+send_keys. Locator mapping for proposals: `css=`→`css:`/By.CSS, `xpath=`→By.XPATH (SeleniumLibrary accepts `css:`/`xpath:` prefixes). Frame support: Selenium has no pierce syntax — frame healing for Selenium is detect + RCA only in this change (explicitly out of scope to heal into frames; documented).

*Alternative rejected*: translating Playwright pierce syntax to Selenium frame-switching sequences — stateful (switch_to.frame) and conflicts with the test's own frame context; not worth it before demand is proven.

### D6: Self-growing eval corpus

`heal corpus harvest <results-glob>` extracts unique ground-truth cases (healed events whose locator resolves uniquely in the recorded DOM — the same mining logic as the exploration probe) into `tests/evals/fixtures/`, deduplicated by (failed_locator, healed_locator, dom-hash). `eval_heal.py` discovers fixtures dynamically. Tier changes (D3 thresholds, prompts) are validated against the corpus before merging.

## Risks / Trade-offs

- [Plausible-but-wrong selections remain possible at Tier 2] → same exposure as today's generation mode (which also picked `#firstname` patterns); mitigated by element-info-rich candidate lists, the corpus regression gate, and RCA records making every heal reviewable.
- [Frame evidence blow-up on frame-heavy pages] → per-frame caps + visibility/origin/size filters; experiment task measures on an ad-heavy page before defaults are fixed.
- [Selection mode worse than generation on exotic DOMs (generator misses the element)] → measured 1/53 miss; Tier 3 fallback retained and exercised by a forced test.
- [Warm-started fixes mask new breakage] → swap only when broken locator still matches 0 elements; events still recorded as healed with `warm-start` attempt provenance so the dashboard shows them.
- [Selenium driver behavioral drift vs Browser driver] → shared atest pages run under both libraries where keywords overlap; protocol conformance test suite parameterized by driver.

## Migration Plan

No breaking changes. Defaults move to the tiered pipeline (`HEAL_LOCATOR_TIERS=selection`); `generation` restores prior behavior. New optional dependency extra: `robotframework-heal[selenium]`. Rollback per feature flag.

## Open Questions

- Frame filter defaults (min size, same-origin only?) — settle in the frame-evidence experiment task.
- Warm-start scope: per source file vs per suite vs global — start per source file (most precise), revisit with history data.
- Should Tier 2's top-K be fixed (e.g. 8) or fuzzy-margin-adaptive? Start fixed, evaluate on the corpus.
