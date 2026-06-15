# Proposal: healed-files-diff-report

## Why

Today healed file copies and diffs only exist when `HEAL_FIX_TIER=patch` is set, the only diff view is a unified `.patch` (machine-oriented), and the dashboard shows fix proposals as bare `old → new` strings. Reviewing what healing *would change* is the primary human workflow after a run — it should not require opting into a fix tier, and it deserves a proper visual diff (the sibling project robotframework-selfhealing-agents ships healed suites + HTML diffs as a headline feature; ours should be at least as good).

Additionally, the fix engine's variable resolution has two known blind spots: arguments with a literal prefix before the variable (`css=${BTN_ID}`) fall back to literal call-site replacement, and locators passed *into user keywords as keyword arguments* (the failing `Click  ${locator}` lives in a resource keyword, but the broken literal lives at the call site in the test) resolve as `unresolved` — the sibling project handles this case.

## What Changes

- **Healed copies + visual diffs become standard report artifacts** (every run with fix proposals, independent of `HEAL_FIX_TIER`): healed `.robot`/`.resource` files are written to `<report dir>/healed_files/` — never replacing the originals — and per-file HTML diffs to `<report dir>/diffs/`. The fix *tiers* keep governing only what touches the user's working tree (`.patch`, in-place).
- **Visually appealing diff view**: self-contained side-by-side HTML diff per healed file with intra-line word-level change highlighting, line numbers, a per-file summary header (locator mappings applied, lines changed), and an index; the dashboard links each fix proposal to its diff and shows a compact inline before/after.
- **Advanced variable replacement** (all via `robot.api.parsing` model transformers):
  - `prefix${VAR}suffix` argument shapes: when the variable's value portion changed, update the variable definition instead of clobbering the call-site token.
  - **User-keyword argument flow**: when the failing keyword call's locator is a keyword argument of the enclosing user keyword, trace one hop to the call sites passing the value and fix the literal (or variable) there — in test files and resource keywords, including imported resources. Multiple matching call sites are all fixed in the healed copies and classified `shared`.
- Healed-copy generation reuses the existing synthesis pipeline (re-parse validation, idempotency, byte-identical untouched lines).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `fix-engine`: origin resolution extended with prefix/variable/suffix shapes and one-hop user-keyword argument call-site tracing; Tier 0 (report) now includes healed copies + visual diffs (working-tree artifacts remain tier-gated).
- `healing-report`: new visual diff report requirement (side-by-side, intra-line highlights, linked from the dashboard, self-contained).

## Impact

- **Code**: `heal/report/diff.py` (new renderer), `heal/report/html.py` (dashboard links/inline diff), `heal/rf/listener.py` (`_write_fixes` always synthesizes copies+diffs; tiers gate patch/in-place only), `heal/fix/resolve.py` (prefix shapes, keyword-argument call-site tracing), `heal/fix/apply.py` (multi-site changes), CLI `heal report`/`apply` reuse.
- **Dependencies**: none added (difflib + existing jinja2).
- **Users**: no breaking changes; more artifacts in the report dir by default. Working tree remains untouched by default — explicitly preserved.
- **Risk**: keyword-argument tracing can mis-attribute call sites → conservative matching (argument value must equal the failed locator after variable resolution), `shared` classification, copies-only by default; corpus/atest regression coverage.
