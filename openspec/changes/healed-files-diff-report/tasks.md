# Tasks: healed-files-diff-report

## 1. Visual diff renderer

- [x] 1.1 Implement `heal/report/diff.py`: side-by-side renderer with coalesced intra-line word highlighting, line numbers, context folding, per-file fix header, self-contained CSS; unit tests incl. edge cases
- [x] 1.2 Diff index page with change counts and links

## 2. Always-on healed copies + diffs

- [x] 2.1 Fix synthesis extracted to `heal.fix.service.build_fix_artifacts`; copies+diffs always produced; `.patch`/in-place tier-gated; original-untouched regression test
- [x] 2.2 Dashboard links each proposal to its diff page + embeds inline changed lines; `heal report` regenerates diffs from a store with graceful skip
- [x] 2.3 Live atest verified: healed copy + diff page + index produced by default, original byte-identical, old/new locators word-highlighted, dashboard linked

## 3. Advanced variable replacement

- [ ] 3.1 `resolve_fix` prefix support: `prefix${VAR}suffix` single-variable shapes update the variable definition when prefix/suffix are preserved in the healed locator; fall back to call-site literal otherwise; unit tests for all split cases
- [ ] 3.2 User-keyword argument tracing: identify enclosing keyword + argument position from the AST (`[Arguments]`, lineno span), scan suite tree for call sites (positional + `name=` named args, normalized keyword-name matching, embedded-arg keywords excluded), match by resolved-value equality; `kind="keyword-argument"` with call-site edit list, `shared` when >1 site or variable target, `unresolved` on zero matches; argument-default fixes when no caller overrides
- [ ] 3.3 `CallSiteReplacer` transformer + multi-edit support in `synthesize_changes`; `FixProposal.usages` carries call sites (dashboard/MCP visible); idempotency + re-parse validation tests on a realistic suite tree (test → resource keyword → broken literal at call site; caller-passes-variable; default-value case)
- [ ] 3.4 Run the fix-engine test suite + eval-corpus locator fixtures to confirm no resolution regressions; extend `heal_locator_drift` atest pages/suite with a keyword-argument scenario healing end-to-end into a correct healed copy

## 4. Docs

- [ ] 4.1 README/features: diff report section (screenshot-free description), variable-replacement coverage table (literal / var / prefix-var-suffix / keyword-arg one hop / not covered: variable files, multi-hop); CHANGELOG entry
