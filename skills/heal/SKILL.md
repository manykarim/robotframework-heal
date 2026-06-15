---
name: heal-triage
description: Triage and permanently fix Robot Framework test failures recorded by robotframework-heal. Use after a test run when heal events exist (an `events.jsonl` in the run's heal report directory), to review healed/unhealed failures, inspect root causes, and apply locator fixes to .robot/.resource files safely.
---

# Healing triage → inspect → fix workflow

robotframework-heal records one event per failed keyword in `<outputdir>/heal/events.jsonl`:
diagnosis (failure class), healing attempts, root-cause analysis, evidence
(DOM excerpt, screenshots, git history of the test file) and — for healed
locator drift — a fix proposal with blast radius.

## Surfaces

Use either the CLI or the MCP server; they expose the same data.

CLI:
- `heal triage <outputdir>` — summary + per-failure RCA and fix proposals
- `heal report <outputdir>` — render `heal_report.html` + `summary.json`
- `heal apply <outputdir> [--patch FILE] [--in-place] [--force]` — apply fixes
- `heal doctor [--role all]` — probe configured model endpoints
- `heal history <history.sqlite>` — locators healed repeatedly (flaky hotspots)
- `heal mcp <outputdir>` — start the MCP server (stdio)

MCP tools (server: `heal mcp <outputdir>`):
- `list_failures` → ids + statuses
- `get_failure_bundle(event_id)` → full evidence bundle
- `get_fix_proposals` → proposals with blast radius + usage sites
- `apply_fix(event_id, in_place=False, force=False)` → patch or in-place result
- `healing_history(db_path)` → cross-run hotspots

## How to work

1. **Triage first**: list failures; healed ones have verified fix proposals,
   unhealed ones have RCA records explaining the likely root cause.
2. **Respect blast radius**: `local` proposals are safe to apply in place.
   `shared` proposals change a variable used at several sites — read the
   usage list, decide whether the *variable* should change or the one
   broken call site should get its own locator, then edit accordingly.
   `apply_fix(in_place=True)` will refuse `shared` on purpose.
3. **Dirty git tree**: in-place application refuses when target files have
   uncommitted changes. Commit/stash first instead of forcing.
4. **Unhealed failures**: read `get_failure_bundle` — the RCA distinguishes
   test-outdated (fix the test) from application-changed/defect (report it).
   The git-history evidence shows when the test last changed.
5. **Repeat offenders**: check `healing_history`; a locator healed in many
   runs needs a permanent fix even if every run "passes".

After applying fixes, run the affected suites to confirm, and propose the
diff to the user before committing.
