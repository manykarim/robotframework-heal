# Tasks: healed-files-diff-report

## 1. Visual diff renderer

- [x] 1.1 Implement `heal/report/diff.py`: side-by-side renderer with coalesced intra-line word highlighting, line numbers, context folding, per-file fix header, self-contained CSS; unit tests incl. edge cases
- [x] 1.2 Diff index page with change counts and links

## 2. Always-on healed copies + diffs

- [x] 2.1 Fix synthesis extracted to `heal.fix.service.build_fix_artifacts`; copies+diffs always produced; `.patch`/in-place tier-gated; original-untouched regression test
- [x] 2.2 Dashboard links each proposal to its diff page + embeds inline changed lines; `heal report` regenerates diffs from a store with graceful skip
- [x] 2.3 Live atest verified: healed copy + diff page + index produced by default, original byte-identical, old/new locators word-highlighted, dashboard linked

## 3. Advanced variable replacement

- [x] 3.1 `resolve_fix` prefix support: `prefix${VAR}suffix` updates the variable when literals preserved, literal fallback otherwise; unit tests
- [x] 3.2 User-keyword argument tracing: enclosing-keyword detection, positional+named call sites, caller-passes-variable, [Arguments] default fixes; search root defaults to the git repo root
- [x] 3.3 `CallSiteReplacer` multi-site edits in `synthesize_changes`; proposal kind/usages enrichment; realistic suite-tree tests
- [x] 3.4 Fix suite green (166 unit tests); live atest: heal inside resource keyword traced to the test-file call site in the healed copy, keyword body untouched, diff generated

## 4. Docs

- [x] 4.1 README fix-target coverage table + artifact docs; CHANGELOG entry
