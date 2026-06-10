# Tasks: agentic-heal-rewrite

Experiment-gated phases: tasks marked **[EXPERIMENT]** must complete (with findings recorded in `experiments/<name>/FINDINGS.md`) before the tasks that depend on them are implemented. Reference backends: MiniMax (`MINIMAX_API_KEY`, `https://api.minimax.io/v1`) and OpenRouter small models (`OPENROUTER_API_KEY`/`OPENROUTER_BASE_URL` in `.env`); prefer small/cheap models in all experiments.

## 1. Foundations (packaging, settings, schemas)

- [x] 1.1 Migrate `pyproject.toml` to PEP 621 with uv (hatchling backend); commit `uv.lock`; keep `SelfHealing` package importable; CI installs via `uv sync`
- [x] 1.2 Create `src/heal/` skeleton (`core`, `drivers`, `rf`, `fix`, `report`, `mcp`, `cli`) with import-linting: `core` imports neither `robot` nor driver libs
- [x] 1.3 Implement `HealSettings` (pydantic-settings, `HEAL_` prefix): per-role model config, budgets, report paths, feature flags; unit tests incl. legacy-kwarg mapping table
- [x] 1.4 Implement core schemas (`FailureContext`, `Diagnosis`, `HealAction`, `HealOutcome`, `FixProposal`, `RcaRecord`, `HealEvent`) — flat agent-facing models per schema-austerity rule; serialization round-trip tests

## 2. Model runtime (gates everything agentic)

- [x] 2.1 **[EXPERIMENT]** MiniMax output-mode matrix (`experiments/minimax-probe/probe.py`): ToolOutput/NativeOutput/PromptedOutput, tool loop, ModelRetry in tool+prompted modes — DONE: native+prompted PASS, all tool-transport paths FAIL on defaults; ModelRetry verified working in prompted mode
- [x] 2.2 **[EXPERIMENT]** Root-cause the tool-mode failures (probe2) and OpenRouter small-model matrix (probe3) — DONE: root cause is forced `tool_choice` (fix: `openai_supports_tool_choice_required=False`, 311s→14s); per-model matrix in FINDINGS.md; exploration tool loops unreliable on all small models; ModelRetry/prompted passes everywhere reachable
- [ ] 2.3 Implement `ModelFactory`: provider resolution (any OpenAI-compatible base_url + pydantic-ai provider strings), per-role `ModelCapabilities` profile resolution with overrides informed by 2.1/2.2 findings
- [ ] 2.4 Implement `build_agent(role, schema)`: generic output-mode wrapping (native/tool/prompted), strict-stripping `prepare_tools` hook, schema-derived prompted templates
- [ ] 2.5 Implement `RunLedger` + per-transaction `UsageLimits`; cap-breach degradation to RCA-only; unit tests with `TestModel`
- [ ] 2.6 Implement endpoint probe library (`heal.core.doctor`): tool-call/strict/JSON/vision probes returning a resolved profile + actionable errors (reuse probe code from experiments)

## 3. Engine and triage

- [ ] 3.1 Implement `SessionDriver` protocol (query/inspect/act primitives) and `BrowserDriver`; port `get_simplified_dom_tree`, unique-selector generation, fuzzy filtering from `SelfHealing/utils.py` with tests
- [ ] 3.2 Implement evidence collectors (RF metadata, simplified DOM excerpt, screenshot, console/network excerpts, git file history — bounded and cached) and lazy `FailureContext` assembly
- [ ] 3.3 Implement the engine pipeline (collect → detect → diagnose → plan → act+verify → RCA) with the failure-class plugin registry and suppression rules (skip-parents, re-entrancy guard, budgets)
- [ ] 3.4 Implement deterministic detectors: element-count-zero, readyState, viewport intersection, open-dialog, required-field state
- [ ] 3.5 Implement triage agent (flat `Diagnosis` schema) invoked only on detector ambiguity; unit tests with `FunctionModel` for both paths
- [ ] 3.6 **[EXPERIMENT]** Threading spike (`experiments/rf-threading/`): persistent healer loop + main-thread driver executor inside a real RF run — prove keyword rerun, return-value assignment, log integrity, timeout unblock; record findings incl. fallback decision (portal/run_sync) if disproven
- [ ] 3.7 Implement the transaction runtime per 3.6 findings: submit/serve queue, per-failure wall-clock cap, engine-owned re-entrancy flag

## 4. RF listener surface (phase-1 usable increment)

- [ ] 4.1 Implement `heal.rf.Listener` (v3): failure qualification by owning library, transaction submission, outcome application (status mutation, assign, log messages)
- [ ] 4.2 Implement `SelfHealing` deprecation shim mapping legacy kwargs (`fix`, `heal_assertions`, `use_llm_for_locator_proposals`, …) to settings; deprecation warnings
- [ ] 4.3 Implement locator-healing plugin: proposal agent (tool-tier aware), validator-based live verification (exists/unique/visible/type-compatible), rerun, greedy fixed-locator reuse
- [ ] 4.4 Implement timing-recovery plugin (wait-until-ready + rerun, no LLM)
- [ ] 4.5 Acceptance test suite (atest): demo web app with seeded locator drift + slow loads; run via shim and new listener; assert healed results and events; wire into CI with `TestModel`-backed dry mode and optional live-model mode
- [ ] 4.6 **[EXPERIMENT]** End-to-end latency/cost measurement of 4.5 against MiniMax and one OpenRouter small model; record per-failure wall-clock; set default `HEAL_MAX_FAILURE_SECONDS` from data

## 5. Run store and reports

- [ ] 5.1 Implement append-only JSONL run store (`HealEvent` per transaction, written at transaction end); rerun merge + dedupe; crash-safety test (kill -9 mid-run)
- [ ] 5.2 Implement HTML dashboard renderer (self-contained: summary, class breakdown, drill-down with screenshots/diffs/cost/model tier); healed AND unhealed events
- [ ] 5.3 Implement `summary.json` + GH annotations output (rewire `utilities/gha_reporter.py`)
- [ ] 5.4 Implement SQLite healing history (per locator/source location) + dashboard hotspot flagging; replaces tinydb locator_db

## 6. Remaining failure classes

- [ ] 6.1 Implement `AppiumDriver` (page-source DOM, swipe, visibility) and register with the listener
- [ ] 6.2 Implement viewport-recovery plugin (scroll into view web / bounded swipe search Appium)
- [ ] 6.3 Implement overlay-recovery plugin (deterministic dismiss heuristics; LLM choice only among verified candidate controls; post-dismiss verification)
- [ ] 6.4 **[EXPERIMENT]** Vision probe (`experiments/vision-probe/`): screenshot Q&A (loading state, modal presence, form errors) on MiniMax vision-capable model + one OpenRouter cheap vision model; gate 6.5/6.6 on findings
- [ ] 6.5 Implement form-diagnosis plugin (DOM required/invalid analysis; vision enrichment when available; diagnose-only default, `HEAL_FORM_FILL` opt-in)
- [ ] 6.6 Implement assertion-healing plugin (drift comparison, semantic-drift guard, verified rerun; `HEAL_ASSERTIONS` opt-in)
- [ ] 6.7 Implement RCA agent + clean-message composition + git test-change context; RCA record for every transaction incl. suppressed/budget-exhausted

## 7. Fix engine

- [ ] 7.1 **[EXPERIMENT]** AST spike (`experiments/rf-ast-fix/`): locator-origin resolution + variable/suffix analysis + cross-file usage scan on this repo's atest suites and one real-world suite; confirm blast-radius computation is reliable
- [ ] 7.2 Implement fix synthesis: AST transformers (keyword-call replacement, variable updates incl. imported resources), origin resolution, blast-radius classification
- [ ] 7.3 Implement Tier 1: healed copies + aggregated unified `.patch` (git-apply verified in tests); re-parse validation + idempotency tests
- [ ] 7.4 Implement Tier 2: opt-in in-place application at end-of-run with dirty-tree refusal
- [ ] 7.5 Dashboard/report integration: per-event fix proposal with diff view and tier

## 8. CLI, MCP, skill

- [ ] 8.1 Implement `heal` CLI (typer): `triage`, `report`, `apply` (tier-aware), `doctor` (per-role probes, redacted config print)
- [ ] 8.2 **[EXPERIMENT]** MCP server spike: pydantic-ai MCP server vs FastMCP for resource (not just tool) exposure; decide and record
- [ ] 8.3 Implement MCP server: run-store resources (failure bundles, fix proposals), `apply_fix` with tier enforcement, healing-history queries; attached mode exposing the driver toolset
- [ ] 8.4 Write the agent skill (triage→inspect→fix workflow over MCP/CLI); verify referenced commands exist
- [ ] 8.5 Replay/eval harness: golden-failure fixtures from serialized `FailureContext`s; pydantic-evals suite per failure class × model tier; publish compatibility matrix in docs

## 9. Migration and cleanup

- [ ] 9.1 Port/retire old code: delete superseded `browser_healing.py`/`visual_healing.py`/`appium_healing.py` paths once atest passes through the new engine; keep shim
- [ ] 9.2 Documentation: README rewrite, `HEAL_*` config reference + legacy migration table, model-compatibility matrix, mkdocs update
- [ ] 9.3 Update process diagrams (`docs/`) to the new pipeline; changelog for 0.4.0 **BREAKING**
