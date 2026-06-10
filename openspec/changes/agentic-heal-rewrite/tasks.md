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
- [x] 2.3 Implement `ModelFactory`: provider resolution (any OpenAI-compatible base_url + pydantic-ai provider strings), per-role `ModelCapabilities` profile resolution with overrides informed by 2.1/2.2 findings
- [x] 2.4 Implement `build_agent(role, schema)`: generic output-mode wrapping (native/tool/prompted), strict/tool_choice quirks handled via backend profile presets (pydantic-ai model profiles), schema-derived prompted templates via PromptedOutput
- [x] 2.5 Implement `RunLedger` + per-transaction `UsageLimits`; cap-breach degradation to RCA-only; unit tests with `TestModel`
- [x] 2.6 Implement endpoint probe library (`heal.core.doctor`): tool-call/strict/JSON/vision probes returning a resolved profile + actionable errors — validated live on MiniMax: all probes PASS through the runtime preset (vs tool-transport FAIL on raw defaults); caught+fixed profile-merge bug

## 3. Engine and triage

- [x] 3.1 Implement `SessionDriver` protocol (query/inspect/act primitives) and `BrowserDriver`; port `get_simplified_dom_tree`, unique-selector generation, fuzzy filtering from `SelfHealing/utils.py` with tests (fixed two latent bugs: nth-of-type identity, fuzz-median alignment)
- [x] 3.2 Implement evidence collectors (RF metadata, simplified DOM excerpt, screenshot, git file history — bounded and cached) and lazy `FailureContext` assembly (console/network collectors deferred to driver support)
- [x] 3.3 Implement the engine pipeline (collect → detect → diagnose → plan → act+verify → RCA) with the failure-class plugin registry and budget suppression (skip-parents + re-entrancy guard live in the listener, task 4.1)
- [x] 3.4 Implement deterministic detectors: element-count-zero, readyState, viewport intersection, open-dialog (required-field state comes with form plugin, 6.5)
- [x] 3.5 Implement triage agent (flat `Diagnosis` schema) invoked only on detector ambiguity; unit tests with `FunctionModel` for both paths
- [x] 3.6 **[EXPERIMENT]** Threading spike (`experiments/rf-threading/`): 4/4 PASS in a real RF run — rerun, return-value assignment, parallel loop work, abandonment unblock all proven; no fallback needed; findings recorded
- [x] 3.7 Implement the transaction runtime per 3.6 findings: `heal.rf.executor.TransactionRuntime` (submit/serve queue, abandonment with grace, `MainThreadProxy`); re-entrancy flag lives in the listener (4.1)

## 4. RF listener surface (phase-1 usable increment)

- [x] 4.1 Implement `heal.rf.HealListener` (v3): failure qualification by owning library, transaction submission, outcome application (status mutation, assign, log messages), greedy fixed-locator reuse in start_keyword
- [x] 4.2 Implement `SelfHealing` deprecation shim mapping legacy kwargs (`fix`, `heal_assertions`, `use_llm_for_locator_proposals`, …) to settings; deprecation warnings
- [x] 4.3 Implement locator-healing plugin: proposal agent (tool-tier aware), validator-based live verification (exists/unique/visible), rerun with candidate fallback, greedy fixed-locator reuse
- [x] 4.4 Implement timing-recovery plugin (wait-until-ready + rerun, no LLM) — done as part of 3.3/3.4 (TimingPlugin)
- [x] 4.5 Acceptance test suite (atest): seeded locator drift (live-llm tag) + slow-load timing (deterministic, no LLM); both green on real Chromium via the shim; wired into CI (`invoke heal-utests` + `invoke heal-atests`; locator suite via `--live-llm` since locator healing inherently needs a model)
- [x] 4.6 **[EXPERIMENT]** Latency measured: MiniMax 18.6s first heal / gpt-4.1-nano 6.9s / greedy reuse 0.2s no-LLM; found+fixed: NativeOutput unreliable under validator loops on MiniMax → preset now prompted; default 60s budget confirmed; findings in minimax-probe/FINDINGS.md

## 5. Run store and reports

- [x] 5.1 Implement append-only JSONL run store (`HealEvent` per transaction, written at transaction end); rerun merge + dedupe; corrupt-tail tolerance test
- [x] 5.2 Implement HTML dashboard renderer (self-contained: summary, class breakdown, drill-down with screenshots/attempts/cost/model tier); healed AND unhealed events; verified in live run
- [x] 5.3 Implement `summary.json` + GH annotations output (`heal.report.summary.gha_annotations`; legacy `utilities/gha_reporter.py` untouched, retired with old flows in 9.1)
- [x] 5.4 Implement SQLite healing history (per locator/source location) + dashboard hotspot flagging; replaces tinydb locator_db

## 6. Remaining failure classes

- [x] 6.1 Implement `AppiumDriver` (page-source XML DOM, bounded swipe search, dismiss candidates) and register with the listener
- [x] 6.2 Implement viewport-recovery plugin (scroll into view web / bounded swipe search Appium, with single-hop fallthrough to locator-drift when swiping finds nothing)
- [x] 6.3 Implement overlay-recovery plugin (deterministic dismiss candidates from driver, post-dismiss verification, rerun; no LLM in default path)
- [x] 6.4 **[EXPERIMENT]** Vision probe (`experiments/minimax-probe/probe5_vision.py`): MiniMax-M3, gemini-2.5-flash-lite, gpt-4.1-nano all PASS loading/form questions (1–8s); gate opened; bool-schema lesson recorded
- [x] 6.5 Implement form-diagnosis plugin (DOM required/invalid analysis; vision corroboration when `HEAL_VISION_MODEL` set; diagnose-only default, `HEAL_FORM_FILL` opt-in with recorded values)
- [x] 6.6 Implement assertion-healing plugin (message parsing, semantic-drift guard incl. numeric magnitude, optional vision check, verified rerun; `HEAL_ASSERTIONS` opt-in)
- [x] 6.7 Implement RCA agent enriching unhealed transactions (template fallback, budget-capped) + git test-change context in evidence; RCA record for every transaction incl. suppressed

## 7. Fix engine

- [x] 7.1 **[EXPERIMENT]** AST spike folded into `tests/unit/fix/` against realistic suite+resource trees and validated live on the heal atest suite (gpt-4.1-nano heal → correct git-appliable patch); blast radius reliable for literal/variable/variable+suffix
- [x] 7.2 Implement fix synthesis: AST transformers (keyword-call replacement, variable updates incl. imported resources), origin resolution, blast-radius classification
- [x] 7.3 Implement Tier 1: healed copies + aggregated unified `.patch` (git-apply verified in tests); re-parse validation + idempotency tests
- [x] 7.4 Implement Tier 2: opt-in in-place application at end-of-run with dirty-tree refusal (force override available); `shared` never auto-applies
- [x] 7.5 Dashboard/report integration: per-event fix proposal with blast radius + usages (listener enrichment), heal.patch + healed copies in report dir

## 8. CLI, MCP, skill

- [x] 8.1 Implement `heal` CLI (typer): `triage`, `report`, `apply` (tier-aware), `doctor` (per-role probes, redacted config print), `history`, `mcp`; verified against a live run store
- [x] 8.2 **[EXPERIMENT]** MCP decision: official `mcp` SDK FastMCP (tools+resources over data; pydantic-ai's MCP server targets exposing agents) — recorded in `heal/mcp/server.py`
- [x] 8.3 Implement MCP server: failure bundles, fix proposals, `apply_fix` with blast-radius/tier enforcement, healing-history queries, events resource (attached live-toolset mode deferred — post-run bundles cover the coding-agent workflow)
- [x] 8.4 Write the agent skill (`skills/heal/SKILL.md`: triage→inspect→fix over MCP/CLI); referenced commands exist
- [x] 8.5 Replay/eval harness: `heal.evals.replay` (ReplayDriver/ReplaySession from serialized contexts), golden fixture exported from a real run, `tests/evals/eval_heal.py` — verified: gpt-4.1-nano replays+heals the fixture offline (3.2s, 612 tokens)

## 9. Migration and cleanup

- [ ] 9.1 Port/retire old code: delete superseded `browser_healing.py`/`visual_healing.py`/`appium_healing.py` paths once atest passes through the new engine; keep shim
- [ ] 9.2 Documentation: README rewrite, `HEAL_*` config reference + legacy migration table, model-compatibility matrix, mkdocs update
- [ ] 9.3 Update process diagrams (`docs/`) to the new pipeline; changelog for 0.4.0 **BREAKING**
