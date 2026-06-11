# Changelog

## 0.4.0 (unreleased) — tiered healing, frames, Selenium

### Added
- **Healed copies + visual diffs as standard report artifacts**: every run with
  fixes writes `healed_files/` and side-by-side HTML `diffs/` (word-level
  highlighting, context folding, per-file fix summary) — read-only, originals
  untouched; the dashboard links and embeds the changed lines. `HEAL_FIX_TIER`
  now gates only `.patch` and in-place edits.
- **Advanced variable replacement**: `prefix${VAR}suffix` arguments update the
  variable definition; locators passed into shared user keywords are traced one
  hop to the call sites (positional and named), the variable they pass, or the
  `[Arguments]` default — the keyword body is never broken for other callers.
- **Frame-aware healing** (Browser): per-frame DOM evidence tagged with pierce
  prefixes, `frame >>> inner` proposals (nested frames supported), and an
  interaction-target blocklist that fixes a demonstrated false heal (the engine
  previously "healed" a locator by clicking the iframe element itself).
- **Tiered locator selection** (default): deterministic candidates + fuzzy
  ranking → LLM index-pick over top-8 with element info → full-DOM generation
  fallback. Corpus-measured: ~70% fewer tokens at equal-or-better accuracy;
  +27 accuracy points on 8B-class models. `HEAL_LOCATOR_TIERS=generation`
  restores the previous behavior.
- **Cross-run heal memory**: known broken→healed mappings warm-start from
  `history.sqlite` (`HEAL_WARM_START`, default true) — repeat heals on later
  runs cost zero LLM tokens; events carry reused-from-history provenance.
- **SeleniumLibrary support** (`pip install robotframework-heal[selenium]`):
  locator drift, timing, viewport, overlay and form diagnosis; frame content
  is explicitly not healable on Selenium (no pierce syntax) and is reported.
- **Self-growing eval corpus**: `heal corpus <results-paths>` harvests
  ground-truth fixtures from recorded heals; the eval runner grades
  element-identity per tier mode and backend.
- `.env` auto-loading (nearest `.env`, overrides environment variables).

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
