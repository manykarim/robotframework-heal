# robotframework-heal

A Robot Framework listener for **failure triage, self-healing and root-cause analysis** of UI tests (Browser/Playwright and Appium).

Every failed keyword is classified into a failure class, healed when possible — and **always** turned into a clean, enriched error record:

| Failure class | What happens |
|---|---|
| `locator-drift` | LLM proposes locators, each **verified live** (exists, unique, visible) before the keyword reruns |
| `timing` | waits for page-ready and reruns — no LLM |
| `viewport` | scrolls (web) or swipe-searches (Appium) the element into view — no LLM |
| `overlay` | dismisses the blocking dialog/banner, verifies, reruns |
| `form-state` | diagnoses unfilled required / invalid fields (DOM + optional screenshot analysis) |
| `assertion-drift` | opt-in: verifies the UI text drifted (semantic-change guard) and reruns with the corrected expectation |
| `unknown` | root-cause analysis only |

Healed or not, each transaction produces a typed event: diagnosis, healing attempts, RCA (including the test file's git history — "test outdated" vs "app changed"), evidence (DOM excerpt, screenshots) and, for healed locators, a **fix proposal with blast radius**.

📙 [Documentation](https://manykarim.github.io/robotframework-heal/)

## Installation

```bash
pip install robotframework-heal
```

## Quickstart

```robotframework
*** Settings ***
Library    Browser    timeout=5s
Library    heal.rf.HealListener
```

Configure the model once in a `.env` file (any OpenAI-compatible endpoint — vLLM, Ollama, LiteLLM proxy, MiniMax, OpenRouter — or a pydantic-ai provider string):

```bash
HEAL_MODEL=MiniMax-M2.5
HEAL_BASE_URL=https://api.minimax.io/v1
HEAL_API_KEY=your-key
```

The nearest `.env` (searched from the working directory upwards) is loaded automatically and **overrides already-set environment variables** — your project's `.env` is the single source of truth for a run.

Check the setup before a run:

```bash
heal doctor --role all
```

`doctor` probes the endpoint (tool calling? strict schemas? JSON mode? vision?) and resolves the best structured-output mode per agent role — small self-hosted models work via the universal prompted-JSON floor.

## Reports

After a run, `<outputdir>/heal/` contains:

- `heal_report.html` — self-contained dashboard (healed *and* unhealed failures, evidence, attempts, costs, repeat-healing hotspots)
- `events.jsonl` — append-only, crash-safe run store (one typed event per failure)
- `summary.json` — for CI gates (e.g. fail the build above a heal-count threshold)
- `heal.patch` + `healed_files/` — git-appliable fixes (with `HEAL_FIX_TIER=patch`)
- `history.sqlite` — cross-run healing history

## Fixing test files

Tiered for safety (`HEAL_FIX_TIER`):

- `report` (default) — proposals shown in the dashboard only
- `patch` — healed copies + a unified `heal.patch` (`git apply heal.patch`)
- `in-place` — edits `.robot`/`.resource` files at end of run; refuses on a dirty git tree; **`shared` blast radius** (a variable used at N call sites) is *never* auto-applied

Or drive it from the CLI / a coding agent:

```bash
heal triage results/          # summary, RCAs, fix proposals
heal apply results/ --in-place
heal mcp results/             # MCP server for coding agents (see skills/heal/)
```

## Configuration (`HEAL_*` environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `HEAL_MODEL` / `HEAL_BASE_URL` / `HEAL_API_KEY` | – | default model for all agent roles |
| `HEAL_TRIAGE_MODEL`, `HEAL_LOCATOR_MODEL`, `HEAL_VISION_MODEL`, `HEAL_RCA_MODEL` (+ `_BASE_URL`/`_API_KEY`/`_OUTPUT_MODE`) | fall back to default | per-role overrides |
| `HEAL_OUTPUT_MODE` | `auto` | `tool` / `native` / `prompted` structured-output transport |
| `HEAL_MAX_FAILURE_SECONDS` | `60` | wall-clock cap per healing transaction |
| `HEAL_MAX_RUN_TOKENS` | `2000000` | run cap; breach degrades to RCA-only |
| `HEAL_FIX_TIER` | `report` | `report` / `patch` / `in-place` |
| `HEAL_HEAL_ASSERTIONS` | `false` | opt-in assertion-drift healing |
| `HEAL_FORM_FILL` | `false` | opt-in form auto-fill (invents test data; values are recorded) |
| `HEAL_ENABLED` | `true` | master switch |

### Migrating from 0.3 (`SelfHealing` library)

`Library    SelfHealing` still works as a deprecated shim routing to the new engine:

| Old | New |
|---|---|
| `LLM_API_KEY` / `LLM_API_BASE` | `HEAL_API_KEY` / `HEAL_BASE_URL` |
| `LLM_TEXT_MODEL` / `LLM_LOCATOR_MODEL` | `HEAL_MODEL` / `HEAL_LOCATOR_MODEL` |
| `LLM_VISION_MODEL` | `HEAL_VISION_MODEL` |
| `heal_assertions=True` | `HEAL_HEAL_ASSERTIONS=true` |
| `locator_db_file=...` | `HEAL_HISTORY_DB=...` |
| `fix=`, `use_locator_db`, `collect_locator_info`, `use_llm_for_locator_proposals` | dropped (run store + capability-resolved proposals replace them) |

## Model compatibility

Capability is **probed, not assumed** (`heal doctor`). Measured on the reference backends (see `experiments/minimax-probe/FINDINGS.md` for the full matrix):

| Backend | Locator heal | Notes |
|---|---|---|
| MiniMax-M2.5 | ✅ ~15s | prompted mode; `tool_choice` quirk handled automatically |
| gpt-4.1-nano (OpenRouter) | ✅ ~4s | cheapest tier works |
| qwen3-14b (OpenRouter) | ✅ slow | no tool endpoints — prompted floor |
| llama-3.1-8b | ⚠️ | verification retry loop converges; triage quality limited |

## Development

```bash
uv sync                  # environment
uv run invoke heal-utests       # unit tests (no LLM, no browser)
uv run invoke heal-atests       # acceptance tests (real browser, no LLM)
uv run invoke heal-atests --live-llm   # + locator healing end-to-end
uv run python tests/evals/eval_heal.py # healing-quality evals (replay, any backend)
```

## Short URL and QR Code

https://tinyurl.com/robot-heal
