# Design: healed-files-diff-report

## Context

The fix engine (`heal/fix/`) already synthesizes healed file contents via `robot.api.parsing` `ModelTransformer`s with re-parse validation and blast-radius analysis, and `write_healed_copies`/`unified_patch` exist — but they run only at `HEAL_FIX_TIER=patch|in-place`, and the only human-facing views are the dashboard's `old → new` strings and a unified patch. Variable resolution (`resolve_fix`) handles literal, `${VAR}`, and `${VAR}suffix` origins; it falls back to literal replacement on `prefix${VAR}` shapes and returns `unresolved` when the "variable" is a user-keyword argument whose value originates at call sites (a case the sibling project handles and real suites hit — e.g. a shared `Click Element With Retry  ${locator}` keyword).

Reference for parity: robotframework-selfhealing-agents ships healed suites + difflib HTML diffs as standard outputs; its diffs are table-based `difflib.HtmlDiff` with injected CSS — functional but dated. We can do better while staying dependency-free.

## Goals / Non-Goals

**Goals:**
- Healed copies + per-file visual diffs as always-on, read-only report artifacts; originals never touched by default.
- A modern, self-contained side-by-side diff (intra-line highlights, line numbers, per-file fix summary), linked from the dashboard.
- Close the two variable-resolution blind spots: `prefix${VAR}suffix` and one-hop user-keyword argument flow.

**Non-Goals:**
- No change to in-place/patch safety semantics (tiers still gate working-tree writes; dirty-tree refusal unchanged).
- No multi-hop dataflow (keyword calling keyword calling keyword) — one hop, conservatively matched.
- No variables defined in Python/YAML variable files (RCA already names the variable; editing non-RF files is out of scope).
- No diffing of files healed only at runtime without fix proposals (e.g. timing recoveries — nothing to change).

## Decisions

### D1: Copies + diffs decouple from fix tiers

`_write_fixes` always resolves proposals and synthesizes healed contents (read-only artifacts under the report dir): `healed_files/<parent>/<name>` and `diffs/<name>.diff.html` + `diffs/index.html`. `HEAL_FIX_TIER` continues to gate only `heal.patch` (Tier patch) and working-tree edits (Tier in-place). Rationale: synthesis is side-effect-free and cheap (<1s, AST on a handful of files); review value is universal; "no direct replacement" is the user's explicit requirement.

*Alternative rejected*: making `patch` the default tier — couples a safety policy (artifact that invites `git apply`) to a reporting concern.

### D2: Own diff renderer over `difflib.SequenceMatcher` opcodes

`heal/report/diff.py` renders side-by-side rows from opcodes at line level, with a second SequenceMatcher pass per `replace` block for intra-line word/char highlighting (`<span class="chg">`). Features: line numbers both sides, unchanged-context folding (3 lines context, expandable `<details>` for folded runs), per-file header (fix mappings `old → new` with blast-radius badges, counts), shared CSS consistent with the dashboard, zero external assets. `difflib.HtmlDiff` (sibling's approach) rejected: table soup, no intra-line granularity worth keeping, hard to restyle.

Dashboard integration: each fix proposal entry links to its file's diff page; the transaction drill-down embeds a compact inline diff (just the changed lines) so the common case needs no navigation.

### D3: `prefix${VAR}suffix` resolution

`resolve_fix` generalizes the argument analysis: split the raw argument into `(prefix, ${VAR}, suffix)` (single-variable shapes only); require `failed_locator == prefix + value + suffix`; compute the new variable value when the healed locator preserves prefix and suffix (`healed[len(prefix):-len(suffix)]`); if either literal part changed, fall back to call-site literal replacement (current behavior). Multiple variables in one argument stay call-site-literal (conservative).

### D4: One-hop user-keyword argument flow

New resolution branch when the failing call's argument token is `${name}` and `name` matches an **argument of the enclosing user keyword** (from `[Arguments]` in the AST — not a Variables-section definition):

1. Identify the enclosing keyword `K` (the failing call's lineno falls within K's span) and the argument position of `${name}`.
2. Scan the suite tree (same root as blast-radius scanning) for calls to `K` (name-insensitive match as RF resolves it; both test bodies and other keywords).
3. A call site matches when its argument at that position (positional or `name=` named) **resolves to the failed locator**: literal equality, or a `${VAR}` whose Variables-section definition equals it (then the fix targets that variable — reusing D3/existing variable logic).
4. All matching sites are fixed in the healed copies; >1 site or a variable target ⇒ `shared`. Zero matching sites ⇒ `unresolved` (RCA keeps naming the keyword argument).

Defaults handled: if the argument has a default equal to the failed locator and no caller overrides it, the fix targets the default value in `[Arguments]`.

*Alternative rejected*: editing the user keyword body to hardcode the healed locator — breaks the keyword for every other caller; exactly the blast-radius mistake the engine exists to prevent.

### D5: Data flow / plumbing

`ResolvedFix` gains `kind="keyword-argument"` with a list of call-site edits (file, lineno, old token, new token) executed by a `CallSiteReplacer` transformer (per file, line-scoped). `synthesize_changes` accepts multi-edit fixes; `FixProposal.usages` carries the call sites so the dashboard/MCP show them. Diff pages are produced from the same `ApplyResult` the patch uses — one synthesis, three renderings (copies, diffs, patch).

## Risks / Trade-offs

- [Call-site mis-attribution] → match requires exact resolved-value equality at the right argument position; ambiguous/no matches stay `unresolved`; artifacts are copies, never the working tree.
- [Keyword name matching vs RF resolution rules (embedded args, library prefixes)] → plain-name + normalized (case/space/underscore-insensitive) matching only; embedded-argument keywords excluded (their "arguments" live in the name).
- [Diff renderer correctness on large files] → context folding caps DOM size; renderer is pure text-in/HTML-out and unit-tested on edge cases (empty file, EOL-less files, unicode).
- [Report dir growth] → healed copies/diffs only for files with actual changes; existing per-run dirs already isolate runs.

## Migration Plan

Additive; no settings change. `HEAL_FIX_TIER` semantics narrow (report tier now also yields copies+diffs) — changelog note. Rollback = revert.

## Open Questions

- Should `heal report` (CLI, post-run) also regenerate diffs from a store on a machine without the original sources? It degrades gracefully (skips synthesis when files are absent) — acceptable for now.
- Named-argument call sites (`locator=css=…`) — included in matching; mixed positional/named edge cases beyond that are excluded until corpus evidence demands them.
