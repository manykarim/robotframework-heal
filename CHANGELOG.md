# Changelog

## 0.4.0 (unreleased) — **BREAKING**: agentic rewrite

Ground-up rewrite as a failure-triage and root-cause-analysis engine built on
pydantic-ai. Full design and experiment evidence:
`openspec/changes/agentic-heal-rewrite/` and `experiments/*/FINDINGS.md`.

### Added
- Failure taxonomy with plugin classes: `locator-drift`, `timing`, `viewport`
  (web scroll + Appium swipe search), `overlay`, `form-state` (diagnose-only by
  default), `assertion-drift` (opt-in, semantic-change guard), `unknown`.
- Verified healing: locator proposals are live-verified (exists/unique/visible)
  inside the agent loop before any rerun.
- Root-cause analysis for every failure (healed or not), including git history
  of the test file; clean error messages instead of raw stack noise.
- Capability-tiered model runtime: per-role models, output-mode ladder
  (tool/native/prompted), backend quirk presets (MiniMax `tool_choice`, vLLM
  strict schemas), budgets/usage ledger, `heal doctor` endpoint probing.
- Reports: crash-safe JSONL run store, self-contained HTML dashboard,
  `summary.json` + GitHub annotations, SQLite cross-run healing history.
- Fix engine over the RF AST: locator-origin resolution (literal / variable /
  variable+suffix incl. imported resources), blast-radius analysis, tiers
  report → `heal.patch` + healed copies → opt-in in-place (dirty-tree refusal).
- New surfaces: `heal` CLI (`triage`, `report`, `apply`, `doctor`, `history`,
  `mcp`), MCP server for coding agents, agent skill (`skills/heal/`).
- Replay/eval harness: recorded failures become offline fixtures
  (`tests/evals/`), measurable per failure class × model tier.

### Changed
- **BREAKING**: configuration moves to `HEAL_*` environment variables
  (pydantic-settings). `LLM_*` variables are no longer read.
- **BREAKING**: packaging migrates to PEP 621 + uv (hatchling); new package
  `heal`; console script `heal`.
- `Library    SelfHealing` keeps working as a deprecation shim routing to the
  new engine; legacy kwargs map to settings where semantics match.

### Removed
- **BREAKING**: litellm-based client, `pyautogui` interactions, tinydb locator
  DB (superseded by the healing history), `fixed_locators.html` (superseded by
  the dashboard), legacy healer modules.
