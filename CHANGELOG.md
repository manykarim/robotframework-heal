# Changelog

## Unreleased

### Added
- **Output-mode safety rule** (`HEAL_PROBE_CAPABILITIES`, default on): heal now
  verifies that the resolved structured-output mode can actually be produced by
  the configured model, and falls back to a mode that can. Backend presets
  resolve a mode per *endpoint*, but capability is per *model* — a reasoning
  model behind a preset pinned to prompted output failed **every** heal while a
  mode it supported sat unused (`qwen3-8b`: 0% → 100% on the eval corpus; live
  browser suites 0/2 → 8/8). Costs one tiny probe call per endpoint, cached for
  the run and shared across roles. The rule only overrides a mode that
  demonstrably *fails* — a working mode is never second-guessed, because probes
  measure transport, not healing quality. Corrections are logged as a warning
  and exposed via `AgentRuntime.capability_notes`; `heal doctor` now prints both
  what the endpoint supports (`probed:`) and what a run would use (`healing:`).
  Evidence: `experiments/small-model-sweep/FINDINGS.md`.
- **Packaged cross-model sweep harness** (`heal.evals.sweep`): replays a
  stratified corpus sample against any OpenAI-compatible backend across models
  and output modes, grading element identity. Samples are spread across suites
  with duplicate actions removed (the previous first-N slice drew 11 of 12
  fixtures from one suite), per-fixture records are retained so aggregates can
  be recomputed without re-running, headline latency excludes unhealed fixtures
  (root-cause analysis fires only there, inflating weak models), ambient
  `HEAL_*` variables are isolated, and wrong-element heals are counted
  explicitly. Report: `experiments/small-model-sweep/FINDINGS.md`.
- **Ollama backend preset**: an Ollama endpoint (detected by the default
  `:11434` port) now resolves an explicit capability profile — prompted
  structured output, tool support treated as unreliable. This is the same floor
  every unknown OpenAI-compatible backend already resolved, so **no healing
  behaviour changes**; the preset makes the default intentional, testable, and
  documented, and gives Ollama-specific quirks a home. Evidence and the
  small-model compatibility matrix: `experiments/ollama-small-models/FINDINGS.md`.
- **Ground-truth conflict detection in the eval corpus**: `heal corpus` now
  rejects a candidate fixture whose truth contradicts an existing fixture for
  the same suite/keyword/args/locator. Fixtures are harvested from heals the
  engine itself performed, so one wrong-but-verified heal could become an
  unwinnable fixture and silently cap corpus accuracy. Selector *form*
  (`#id` vs `tag#id`) and nested targets (`button > i`) are not conflicts.

### Changed
- **Token usage is recorded on unhealed locator transactions, and accumulates
  across tiers.** Previously only a successful heal reported its cost, and a
  selection-tier pick that failed to rerun was never charged at all. Failed
  heals now count toward `HEAL_MAX_RUN_TOKENS`, so a run dominated by failures
  reaches the run budget — and degrades to RCA-only — sooner than in 0.4.0.
  Raise `HEAL_MAX_RUN_TOKENS` if you relied on the previous accounting.

### Fixed
- Removed eval fixture `ait-llm-4bdcdc82db6f7d1d`, which recorded
  `input#firstname` as ground truth for `Fill Text  id=last_name` — an
  artifact of a wrong heal that passed live verification. It capped the
  12-fixture sweep subset at 11/12.
- Corrected the Ollama tool-probe count in the docs (7 of 9 models report no
  tool endpoint, not 8) and scoped the small-model matrix to what was actually
  measured: locator-drift healing on 12 fixtures from a single suite.

## 0.4.0 — 2026-06-18

Ground-up rewrite as a failure-triage and root-cause-analysis engine built on
pydantic-ai (full design and experiment evidence:
`openspec/changes/archive/` and `experiments/*/FINDINGS.md`).

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
- **Failure taxonomy** with plugin classes: `locator-drift`, `timing`,
  `viewport` (web scroll + Appium swipe search), `overlay`, `form-state`
  (diagnose-only by default), `assertion-drift` (opt-in, semantic-change
  guard), `unknown`.
- **Verified healing**: locator proposals are live-verified
  (exists/unique/visible) inside the agent loop before any rerun.
- **Root-cause analysis** for every failure (healed or not), including git
  history of the test file; clean error messages instead of raw stack noise.
- **Capability-tiered model runtime**: per-role models, output-mode ladder
  (tool/native/prompted), backend quirk presets (MiniMax `tool_choice`, vLLM
  strict schemas), budgets/usage ledger, `heal doctor` endpoint probing.
- **Reports**: crash-safe JSONL run store, self-contained HTML dashboard,
  `summary.json` + GitHub annotations, SQLite cross-run healing history.
- **Surfaces**: `heal` CLI (`triage`, `report`, `apply`, `doctor`, `history`,
  `corpus`, `mcp`), MCP server for coding agents, agent skill (`skills/heal/`).

### Changed
- **BREAKING**: configuration moves to `HEAL_*` environment variables
  (pydantic-settings). `LLM_*` variables are no longer read.
- **BREAKING**: packaging migrates to PEP 621 + uv (hatchling); new package
  `heal`; console script `heal`.
- **Canonical listener import is `Library    Heal`.** `Library
  heal.rf.HealListener` (fully-qualified) and `Library    SelfHealing`
  (deprecated 0.3 shim, maps legacy kwargs to settings) also work.

### Removed
- **BREAKING**: litellm-based client, `pyautogui` interactions, tinydb locator
  DB (superseded by the healing history), `fixed_locators.html` (superseded by
  the dashboard), legacy healer modules.
