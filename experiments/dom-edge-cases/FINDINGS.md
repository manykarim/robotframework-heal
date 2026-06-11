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
