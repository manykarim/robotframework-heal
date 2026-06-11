# Findings: shadow DOM and iframe edge cases

**Date**: 2026-06-11 · live engine (gpt-4.1-nano), real Chromium · `edge_cases.robot`, `frame_probe.py`

## Shadow DOM

| Case | Result |
|---|---|
| Broken locator, target 2 open shadow roots deep | **HEALED** — `css=button#shadow-submit` proposed from the flattened serializer DOM, verified, clicked |
| Element in a closed shadow root | fails safely (invisible to serializer and selectors; RCA-only) |

The existing design composes correctly: the `_FULL_HTML_SCRIPT` serializer flattens
open shadow roots into the DOM evidence, and Playwright's CSS engine pierces open
shadow roots natively, so flat selectors proposed from the flattened DOM verify and
execute. **No work needed for open shadow DOM; closed roots are unhealable by
platform design.**

## iframes — FALSE HEAL (correctness hole)

Broken locator targeting a button inside an iframe:
the engine "healed" it to **`css=iframe#content-frame` — clicking the iframe
element itself**. The click succeeds, the rerun passes, the keyword is marked
healed, and the real failure surfaces downstream at the next keyword. Three
stacked gaps:

1. `get_page_source` returns the main frame only → frame content absent from DOM evidence
2. nothing excludes `<iframe>` as a click/fill proposal target → verification passes
3. proposals never use Playwright's frame-piercing syntax

`frame_probe.py` confirmed the repair ingredients all exist:

| Capability | Result |
|---|---|
| `get_element_count("id=frame >>> id=inner")` | works (1) |
| `get_element_states` through `>>>` | works |
| frame DOM via `evaluate_javascript("frame >>> css=html", outerHTML)` | works |
| frame enumeration from main DOM (bs4) | works |

**Consequence**: frame-aware healing is a driver + prompt change with NO engine
changes — serialize each frame's DOM into the evidence tagged with its pierce
prefix, teach the locator prompt the `frame >>> inner` syntax (the existing
validator verifies pierced selectors unchanged via `count`), and blocklist
`iframe`/`frame` tags as interaction targets. The blocklist alone fixes the
false heal and should land first.

## Frame-evidence sizing (task 1.2, `frame_sizing_probe.py`, frame_heavy.html)

| Frame | visible | bbox | serialize | chars | time |
|---|---|---|---|---|---|
| main-content | yes | 604×304 | ok | 341 | 0.24s |
| pixel | yes | 5×5 | ok | 341 | 0.11s |
| hidden (display:none) | no | none | ok | 341 | 0.10s |
| nested-outer | yes | 504×254 | ok | 203 | 0.14s |
| cross-origin (example.com) | yes | 304×104 | **ok** | 544 | 0.12s |

- Serialization is cheap (≈0.1–0.2s/frame); cost is bounded by content size, not frame count.
- **Two-level piercing works**: `outer >>> inner >>> css=html` serializes and
  `outer >>> inner >>> id=btn` counts (1) — nested frames need no special handling
  beyond chained prefixes.
- **Cross-origin frames ARE serializable** through Playwright (CDP is not bound by
  same-origin policy) — the same-origin filter from the design is unnecessary.

**Settled defaults (design D2 updated by evidence):** include frames that are
visible AND have a bounding box ≥ 20×20 px; depth ≤ 2; frames ordered by area
descending, capped at 5 frames; per-frame DOM share = MAX_DOM_CHARS/4, total
evidence still bounded by MAX_DOM_CHARS. Hidden and pixel-sized frames are
skipped (their content is non-interactable or tracking noise).
