# Proposal: agentic-heal-rewrite

## Why

robotframework-heal heals broken locators well, but its architecture has hit a wall: failure detection is string-matching on Playwright error messages, healing logic is an if/elif tree inside a listener callback, ~40% of LLM-facing code fights JSON formatting by hand, and prototyped capabilities (modal dismissal, page-ready waits, Appium swiping, visual assertion checks) are buried as special cases that cannot be extended, tested, or trusted. The sibling project robotframework-selfhealing-agents validates the pydantic-ai direction but demonstrates the failure modes to avoid (LLM-based orchestration, listener re-entrancy state machines, token-blind prompts, broken small-model support).

A ground-up rewrite turns the tool from a "locator healer" into a **failure triage and root-cause-analysis agent**: every failure — healed or not — produces a typed diagnosis, an enriched error record, and where possible a verified fix proposal, delivered through four surfaces (RF listener, MCP server, CLI, coding-agent skill).

## What Changes

- **BREAKING**: New package `heal` replaces the `SelfHealing` internals. A thin `SelfHealing` listener shim is kept for backward-compatible imports, but configuration moves to typed `HEAL_*` environment settings (pydantic-settings) and the old kwargs are deprecated.
- **BREAKING**: Build/dependency management migrates from Poetry to uv (PEP 621 `pyproject.toml`). `litellm` is replaced by pydantic-ai's provider layer (any OpenAI-compatible endpoint — vLLM, Ollama, LiteLLM proxy, MiniMax — remains supported via `base_url` config).
- New **failure taxonomy**: deterministic detectors + a single-shot triage agent classify failures into `locator-drift`, `timing`, `viewport`, `overlay`, `form-state`, `assertion-drift`, `unknown` — replacing error-message string matching. Failure classes are plugins (detect / heal / synthesize-fix), so new classes are additive.
- New **healing engine** with an explicit per-failure transaction pipeline (collect evidence → detect → diagnose → plan → act+verify → RCA), orchestrated in code; LLM agents (triage, locator, vision, RCA) are typed leaf workers built once and reused. A persistent background event loop + main-thread driver executor replaces per-failure `run_until_complete` and listener re-entrancy.
- New healing capabilities beyond locators: wait-for-ready recovery, scroll/swipe-into-view (web + Appium), overlay/modal dismissal, missing-mandatory-field diagnosis (DOM + screenshot), assertion-drift analysis.
- New **root-cause analysis**: every failure produces a clean, enriched error record with evidence (DOM excerpt, screenshots, console/network hints, test-file git history) and a suggested permanent fix.
- New **capability-tiered model runtime**: per-role model config, automatic output-mode selection (tool / native / prompted) with graceful degradation for small or restricted backends (vLLM strict-mode rejection, missing function calling, inline `<think>` blocks), run-level token/cost budgets, and a `heal doctor` endpoint probe. Validated by experiments against MiniMax before each capability is built.
- New **fix engine**: RF-AST-based rewriting of `.robot`/`.resource` files with locator-origin resolution (literal / keyword / variable / imported resource), blast-radius analysis, and tiered application: report → healed copies + unified `.patch` → opt-in in-place fix → delegated to a coding agent.
- New **reporting**: append-only JSONL run store feeding a self-contained HTML dashboard, side-by-side diffs, machine-readable summary, and cross-run healing history; healed and unhealed failures both appear.
- New **delivery surfaces**: `heal` CLI (`triage`, `report`, `apply`, `mcp`, `doctor`), an MCP server exposing the same toolsets and failure bundles to coding agents, and an agent skill documenting the workflow.
- New **replay/eval harness**: serialized failure contexts become fixtures; healing quality is measurable per failure class × model tier (pydantic-evals), and agent logic is unit-testable without a browser or LLM (`TestModel`/`FunctionModel`).

## Capabilities

### New Capabilities

- `failure-triage`: evidence collection and classification of failed keywords into failure classes (deterministic detectors first, triage agent fallback), with suppression rules (skip-parent keywords, budgets, re-entrancy guard).
- `locator-healing`: locator-drift healing — proposal generation, live-session verification inside the agent loop, keyword rerun, greedy reuse of known fixes.
- `runtime-recovery`: deterministic recoveries — wait-until-ready (timing), scroll/swipe-into-view (viewport, web + Appium), overlay/modal dismissal.
- `form-diagnosis`: missing/invalid mandatory-field analysis via DOM + screenshot; diagnose-only by default, auto-fill behind explicit opt-in.
- `assertion-healing`: assertion-drift detection and verified adjustment proposals using vision + text agents.
- `root-cause-analysis`: enriched, human-readable error records for every failure, including runtime evidence and test-change (git) context.
- `model-runtime`: provider-agnostic model factory, per-role capability profiles, output-mode degradation ladder, budgets/usage ledger, endpoint probing (`doctor`).
- `fix-engine`: AST-based fix synthesis for `.robot`/`.resource`/variable files with blast-radius classification and tiered application (report / patch / in-place / delegated).
- `healing-report`: JSONL run store, HTML dashboard, diff views, summary JSON, cross-run history.
- `rf-listener`: the Robot Framework listener surface — threading/execution model, result mutation, return-value assignment, back-compat shim.
- `mcp-server`: MCP mode exposing driver toolsets, failure bundles, and fix application to coding agents.
- `heal-cli`: command-line surface (`triage`, `report`, `apply`, `mcp`, `doctor`).

### Modified Capabilities

None — this is the first OpenSpec change; no existing specs.

## Impact

- **Code**: new `src/heal/` package (core, drivers, rf, fix, report, mcp, cli); `src/SelfHealing/` reduced to a deprecation shim. Existing `utils.py` DOM heuristics (simplified DOM tree, unique-selector generation, fuzzy filtering) are ported into `heal.drivers`, not discarded.
- **Dependencies**: + `pydantic-ai-slim` (openai/anthropic extras), `pydantic-settings`, `fastmcp` (or pydantic-ai MCP server support), `typer` (CLI); − `litellm`, `pyautogui` (replaced by driver-level actions), `parsimonious`/`cssify` review during port. Python ≥ 3.10 retained.
- **Tooling**: uv-managed environment and lockfile; experiments live in `experiments/` with their own uv projects; MiniMax (`MINIMAX_API_KEY` in `.env`, OpenAI-compatible endpoint `https://api.minimax.io/v1`) is the reference backend for capability-ladder experiments.
- **Users**: listener usage (`-L SelfHealing` / library import) keeps working with deprecation notices; `.env`-based configuration changes names (migration table in docs); reports move from `fixed_locators.html` to the new report directory.
- **Risk**: threading model (background loop + main-thread driver executor) and small-model structured-output behavior are the two riskiest assumptions — both are gated by experiments before dependent phases start (MiniMax probe suite in `experiments/minimax-probe/`).
