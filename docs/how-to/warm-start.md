# Reuse fixes across runs

Within a run, heal remembers each broken→healed locator and swaps it proactively
on the next occurrence (no second LLM call). **Warm start** extends that across
runs by loading known fixes from the healing history.

## How it works

At the first qualifying failure, heal loads recent healed mappings (scoped per
source file) from `history.sqlite`. When a known-broken locator appears again and
still matches nothing, heal swaps it **before** the keyword runs — skipping both
the keyword timeout and the LLM entirely. Every swap is verified live
(broken matches 0, healed matches 1), so a stale mapping simply falls through to
normal healing.

```text
run 1:  Click id=login-button  → heal → css=#signin-btn   (LLM, ~5s)
run 2:  Click id=login-button  → warm swap → css=#signin-btn   (0 tokens, ~0s)
```

## Enable a stable history location

Warm start is **on by default** (`HEAL_WARM_START=true`), but the default history
lives under the run's output directory — which changes per run. Point it at a
stable path so it survives:

```bash
HEAL_HISTORY_DB=.heal/history.sqlite
```

Now a second CI run heals known breakages with **zero tokens**. Reused swaps are
recorded as events (marked reused-from-history) so they still appear in the
report and `summary.json`.

## Inspect repeat offenders

```bash
heal history .heal/history.sqlite
```

Locators healed repeatedly are maintenance hotspots — fix them permanently with
[Fix test files](fixing-files.md).
