# Design: agentic-heal-rewrite

## Context

robotframework-heal v0.3 is a Robot Framework listener that heals broken Browser/Appium locators via litellm completions. Its constraints and pain points:

- Failure detection is substring matching on Playwright error messages (`'waiting for' in message`).
- Healing logic lives in an if/elif tree inside `_end_library_keyword`; prototyped recoveries (modal dismissal, page-ready wait, swipe-into-view, visual assertion checks) are special cases that can't be tested or extended independently.
- LLM interaction is raw chat completions with hand-rolled JSON repair (regex brace fixing, retry loops).
- `BrowserHealer` is a broken singleton re-`__init__`ed per keyword; healing cannot be tested without a live browser + live LLM.

The sibling project robotframework-selfhealing-agents (MarketSquare) validates pydantic-ai for this domain and contributes proven ideas (RF-AST file rewriting, report chain, typed config), but also demonstrates anti-patterns confirmed by its own follow-up branch (`feature/improve_nonopenai_model_function_calls`): an LLM "orchestrator" later deprecated in favor of programmatic routing; healing control flow via listener re-entrancy and shared mutable flags; `asyncio.get_event_loop().run_until_complete()` in a sync listener; agents rebuilt per failure; whole source files and DOM trees pasted into prompts against a 6k token cap; structured output that breaks on vLLM (strict tool definitions rejected) and on small models (no reliable function calling).

Hard constraints for the rewrite:

1. RF listener callbacks are synchronous; Browser/Selenium/Appium library instances are only safe on RF's main thread.
2. pydantic-ai is async-first; agents should be built once and reused.
3. Target deployments include self-hosted small models (vLLM, Ollama, MiniMax, LiteLLM proxies) — GPT-class tool calling cannot be assumed. MiniMax (OpenAI-compatible, `https://api.minimax.io/v1`, key in `.env` as `MINIMAX_API_KEY`) is the reference experiment backend; its M2.5 model emits inline `<think>…</think>` blocks, making it a good worst-case for output parsing.
4. Healing runs inside other people's CI — latency, token cost, and source-file safety are first-class concerns.
5. Assumptions must be validated by experiments (in `experiments/`, uv-managed) before dependent phases are built.

## Goals / Non-Goals

**Goals:**

- A failure-class taxonomy with plugin extension points, replacing string matching.
- Every failure (healed or not) yields a typed RCA record with enriched, clean error messaging.
- Verified healing: no fix is reported without live-session verification.
- Works across model tiers: GPT/Claude-class down to small self-hosted models, with measured (not assumed) degradation.
- Four delivery surfaces over one core: RF listener (realtime), MCP server, CLI, agent skill.
- Safe source-file fixing with blast-radius awareness and tiered application.
- Healing logic unit-testable without browser or LLM; quality measurable per failure class × model tier.

**Non-Goals:**

- No SeleniumLibrary driver in the first release (the driver protocol must make it cheap to add; port priority is Browser, then Appium).
- No multi-agent "collaboration" — agents never call agents.
- No auto-filling of form data by default (diagnose-only; fill is opt-in).
- No support for RF < 6 / listener API v2.
- No attempt to heal non-UI failures (API/database keywords) in this change.

## Decisions

### D1: pydantic-ai as the agent framework

Typed agents with structured outputs eliminate the JSON-repair code wholesale; output validators + `ModelRetry` give verification-in-the-loop; model-agnostic providers cover OpenAI/Azure/Anthropic/Ollama/vLLM/MiniMax via one config shape; MCP is supported both as client and server; `TestModel`/`FunctionModel` + pydantic-evals enable offline testing and quality measurement. Lightweight enough to embed in a listener.

*Alternatives*: LangGraph (durable graph runtime is overhead — our workflow is a short-lived per-failure transaction inside a listener callback); OpenAI Agents SDK (ecosystem gravity, weaker self-hosted story); CrewAI (role-play model mismatched); vendor SDKs (lock-in unacceptable for enterprise self-hosted users). litellm retained only as a *server-side* option (users may point `base_url` at a LiteLLM proxy); the in-process litellm dependency is dropped.

### D2: Orchestration is code; agents are leaf workers

The engine pipeline — collect → detect → diagnose → plan → act+verify → RCA — is deterministic Python. Four agents (triage, locator, vision, RCA), each: typed input, flat typed output, built once at runtime startup, reused all run. No agent invokes another agent.

*Evidence*: the sibling project's LLM orchestrator routed to exactly one tool and was deprecated by its own authors ("programmatic routing instead of LLM-based delegation"). An LLM round-trip for routing adds latency, cost, and nondeterminism with zero information gain.

### D3: Failure classes are plugins

```python
class FailureClassPlugin(Protocol):
    id: str                                   # "locator-drift", "timing", ...
    def detect(ctx: FailureContext) -> Verdict          # deterministic, cheap, NO LLM
    async def heal(ctx, session, runtime) -> HealOutcome
    def synthesize_fix(outcome) -> FixProposal | None
```

Registered in priority order. The deterministic `detect` tier resolves the cheap majority (element count, readyState, viewport intersection, open dialogs, required-field DOM state); the **triage agent** (single-shot, small model, flat `Diagnosis` schema) runs only when detectors are silent or ambiguous. `unknown` falls through to RCA-only.

*Alternative*: keep a dispatch tree in the engine — rejected; it recreates the current unmaintainable if/elif and makes failure classes non-additive.

### D4: Threading model — persistent healer loop + main-thread driver executor

A dedicated thread runs one long-lived asyncio loop hosting the engine and agents. The listener submits a transaction and then *services a request queue while blocked*: any driver/RF call the engine needs (DOM query, screenshot, keyword rerun) is marshalled back and executed on the RF main thread; everything async (LLM calls, evidence collection fan-out) runs on the healer loop.

```
RF MAIN THREAD                          HEALER THREAD (persistent asyncio loop)
end_keyword(failure)                    engine.run(transaction)
  submit job ───────────────────────►     agents + evidence collectors (parallel)
  serve while blocked:                    needs DOM / screenshot / rerun?
    driver_request? execute, reply ───►   continue with result
    done? ◄──────────────────────────   HealOutcome + RcaRecord
  apply outcome (status/assign), emit event
```

Re-entrancy guard: while a transaction is active, listener events triggered by our own keyword reruns are ignored (a flag the engine owns — not scattered booleans).

*Alternatives*: `Agent.run_sync` per failure (fresh loop each failure, no parallelism, fragile when other components own loops — the sibling's bug class); `nest_asyncio` (monkey-patching, unmaintained); driver calls directly from the healer thread (Browser library is not thread-safe — corrupts its node websocket state). The CLI/MCP surfaces reuse the same engine without the marshalling (no RF thread constraint).

*Validation*: phase-1 experiment must prove keyword rerun via `BuiltIn().run_keyword` from inside the served-queue pattern, including return-value assignment and log integrity.

### D5: Capability-tiered model runtime

Per-role (`triage`/`locator`/`vision`/`rca`) model config resolves to a `ModelCapabilities` profile: `tools: none|unreliable|reliable`, `structured_output: tool|native|prompted`, `vision: bool`, `context_budget: int`. Resolution order: pydantic-ai built-in model profiles → user overrides (`HEAL_*` env) → optional runtime probe (`heal doctor` fires tiny calls: tool-call test, strict-schema test, JSON test, vision test) with persisted results.

Two consequences shape the agents:

- **Verification lives in output validators, exploration tools are additive.** `ModelRetry` from an output validator works in *every* output mode, including `PromptedOutput` on toolless models — so live-session verification (locator exists, unique, visible, type-compatible) is universal. Exploration tools (`query_dom`, `get_element_info`) are registered only when `tools == reliable`; weaker models get a richer pre-curated DOM excerpt instead.
- **Output mode is a generic runtime service**: `runtime.build_agent(role, schema)` wraps any schema in the right mode (native/tool/prompted) for the resolved profile — unlike the sibling branch's single hardcoded prompted-template constant. Strict-mode stripping (vLLM rejects `strict: true` / `additionalProperties: false`) is applied via model profile + `prepare_tools` hook.

**Schema austerity rule**: every agent output schema is flat — string enums, no unions, ≤1 nesting level, optionals truly optional. Rich structures (`FixProposal`, `RcaRecord`) are assembled by engine code from small typed pieces.

**Budgets**: pydantic-ai `UsageLimits` per transaction; a run-level `RunLedger` accumulates tokens/cost/wall-clock with caps (`HEAL_MAX_FAILURE_SECONDS`, `HEAL_MAX_RUN_TOKENS`); exceeding a cap degrades to RCA-only mode rather than failing the run. The report labels each event with the model tier and output mode used ("healed via prompted-mode fallback, confidence medium").

*Validation*: the MiniMax probe suite (`experiments/minimax-probe/`) gates this design — see Experimental Evidence below.

### D6: Evidence model — immutable, lazy, curated

`FailureContext` is assembled per transaction by cost-tagged collectors (RF metadata: free; simplified DOM: cheap; screenshot: medium; console/network logs: medium; git history of the test source: cheap, cached per file). Collectors run only as the active tier requires; everything is serializable, making every real failure a replayable fixture. Prompts receive *curated excerpts* (simplified DOM via the ported `get_simplified_dom_tree`, relevant source lines ±10, last N console errors) — never whole files.

### D7: Fix engine — RF AST, blast radius, tiered application

Fix synthesis uses `robot.api.parsing` `ModelTransformer`s (adopting the sibling's proven approach: keyword-call locator replacement; `${VAR} suffix` argument analysis; variable updates propagated to imported `.resource` files). Two hardenings on top:

- **Blast radius**: before changing a variable definition, cross-reference all usages across the parsed suite tree. `local` (literal in one call) → eligible for auto-apply; `shared` (variable used in N places) → demoted to patch/delegated tier with the usage list attached to the proposal.
- **Tiered application**: Tier 0 report (always) → Tier 1 healed copies + unified `.patch` (git-appliable) → Tier 2 in-place edit, opt-in, refused on dirty git tree, executed only at end-of-run → Tier 3 delegated: the MCP/skill surface hands `FixProposal` + evidence to a coding agent for judgment calls (variable vs usage, related comments, untested files).

*Alternatives*: regex/string replacement (breaks on RF syntax variants); LLM-rewrites-the-file (unreviewable, blast radius unbounded).

### D8: Reporting — append-only run store + renderers

During the run, every transaction appends one JSON line (`HealEvent`: diagnosis, evidence refs, attempts, outcome, fix proposal, model tier, cost) to `<output_dir>/heal/events.jsonl` — crash-safe, no end-of-run state loss, mergeable across `--rerunfailed` (adopt the sibling's dedupe-on-merge). Renderers consume the store: self-contained HTML dashboard (summary, failure-class breakdown, per-event drill-down with before/after screenshots and diffs), `summary.json` for CI gates, GH annotations (existing `gha_reporter.py` rewired), unified `.patch`. Cross-run history (healing frequency per locator — flakiness signal) persists in a small SQLite db, replacing tinydb.

### D9: One toolset, four surfaces

`heal.drivers` defines a `SessionDriver` protocol (query/inspect/act primitives); `BrowserDriver` and `AppiumDriver` implement it. pydantic-ai toolsets wrap the driver once and are (a) registered on in-process agents, (b) exposed by the MCP server, alongside resources (failure bundles, fix proposals from the run store) and an `apply_fix` tool gated by blast-radius tier. The CLI (typer) provides `triage` (post-run, over output.xml + store), `report`, `apply`, `mcp`, `doctor`. The agent skill is documentation over the MCP/CLI surface, shipped in-repo.

### D10: Packaging and migration

uv-managed PEP 621 `pyproject.toml` (hatchling backend), `uv.lock` committed. Layout: `src/heal/{core,drivers,rf,fix,report,mcp,cli}` with `core` importing neither `robot` nor any driver. `src/SelfHealing/` becomes a shim re-exporting the listener with a deprecation warning; old `__init__` kwargs map onto new settings where possible. Python ≥ 3.10. Experiments live in `experiments/<name>/` as independent uv projects so probe dependencies never leak into the package.

### D11: Experiment-gated development

Each phase with a risky assumption starts with an experiment task whose findings are recorded in `experiments/<name>/FINDINGS.md`; the dependent design point is confirmed or revised before implementation proceeds. Reference backend: MiniMax via OpenAI-compatible endpoint. Gates: output-mode matrix (done, below), threading/rerun spike (phase 1), DOM-curation token budget check (phase 1), vision probe (phase 2), AST blast-radius spike on real suites (phase 3).

### Experimental Evidence (probe runs, 2026-06-10, pydantic-ai 1.107.0)

Full data and per-model matrix: `experiments/minimax-probe/FINDINGS.md`. Headlines that gate this design:

- **MiniMax-M2.5, defaults**: all tool-transport paths FAIL (`Exceeded maximum output retries`) while NativeOutput and PromptedOutput PASS; the model emits inline `<think>` blocks which pydantic-ai's prompted path handles. Raw curl proved tool calling works at the API level.
- **Root cause (probe 2)**: forced `tool_choice` — with `openai_supports_tool_choice_required=False` the same tasks go from 311s-flaky/642s-FAIL to 12–17s PASS. Strict-stripping alone did not help (it remains relevant for vLLM, which is a different failure).
- **ModelRetry verification via output validator passed everywhere it could run** — MiniMax prompted mode (2 attempts → corrected locator) and 4/4 reachable OpenRouter small models (gpt-4.1-nano, gemini-2.5-flash-lite, qwen3-14b, llama-3.1-8b; the last needing 3 attempts). The verify-in-the-loop principle is confirmed independent of tool support.
- **OpenRouter matrix**: failure *kinds* differ per model — transport (qwen3-14b: no tool-supporting endpoints, 404), quality (flash-lite passes tool transport but misclassifies in prompted mode), availability (ministral-8b: no endpoints). Exploration tool loops were the least reliable path on every model tested.
- **Latency variance 0.7s–311s for the same task** across backends/modes → per-failure wall-clock caps are mandatory; small fast models (nano/flash-lite class) are the right default triage tier.

Consequences folded into D5: per-model probed capability profiles (not provider-level assumptions), backend profile presets (MiniMax: `tool_choice_required=False`; vLLM: strict-stripping), verification in validators as the universal floor, exploration tools gated to probed-reliable models only.

## Risks / Trade-offs

- [Threading model is novel and load-bearing] → Phase 1 spike with a real RF run before any other phase builds on it; fallback design documented (single-threaded portal with `run_sync` and no parallel evidence collection — slower but safe).
- [Small-model healing quality may be poor even when transport works] → eval corpus measures quality per class × tier; report labels degraded modes; docs publish the compatibility matrix instead of overpromising.
- [In-place file fixing can destroy user code] → tier 2 off by default, refused on dirty git tree, end-of-run only, every change also emitted as `.patch`; blast-radius `shared` never auto-applies.
- [Latency per failure in CI] → deterministic detectors resolve common cases LLM-free; per-failure wall-clock cap with degrade-to-RCA; greedy reuse of known fixes ported from current code.
- [Healing masks real regressions] → RCA record always produced; report distinguishes "healed" from "passed"; CI summary supports failing the build on heal-count thresholds.
- [Scope: 12 capabilities is a large surface] → phases ship independently usable increments; phase 1 alone (triage + locator + timing + report skeleton) replaces current functionality.
- [pydantic-ai API churn] → pin minor version in lock; runtime isolates pydantic-ai imports to `core/runtime.py` and `drivers/toolsets.py`.

## Migration Plan

1. Phase 1 lands on `rewrite/agentic-heal` branch; `SelfHealing` shim keeps existing suites green (CI: run the existing utest/atest suites against the shim).
2. Pre-1.0 releases publish both entry points; README documents the `HEAL_*` config migration table (old kwarg → env var).
3. Old code paths deleted once the atest suite passes via the new engine for Browser + Appium; version bumped to 0.4.0 with **BREAKING** changelog.
4. Rollback: the shim and old package coexist on the branch until the final phase; reverting = repointing the listener import.

## Open Questions

- Selenium driver: demand exists (sibling project supports it) — phase 5 or community contribution after the driver protocol stabilizes?
- Default failure-latency budget (`HEAL_MAX_FAILURE_SECONDS`): 30s? 60s? Needs measurement in phase 1 against MiniMax-class latencies (reasoning models are slow; first probe call ~25s).
- Should `heal doctor` results auto-persist and auto-configure the ladder, or print recommendations only?
- MCP server: pydantic-ai's MCP server support vs. plain FastMCP — decide in phase 4 experiment based on resource (not just tool) exposure needs.
