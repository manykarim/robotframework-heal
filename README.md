# robotframework-heal

A Robot Framework listener for **failure triage, self-healing and root-cause analysis** of UI tests (Browser/Playwright, SeleniumLibrary and Appium).

Every failed keyword is classified into a failure class, healed when possible — and **always** turned into a clean, enriched error record:

| Failure class | What happens |
|---|---|
| `locator-drift` | tiered: deterministic candidates → LLM picks (verified live) → full-DOM fallback; elements inside iframes heal via `frame >>> inner` selectors |
| `timing` | waits for page-ready and reruns — no LLM |
| `viewport` | scrolls (web) or swipe-searches (Appium) the element into view — no LLM |
| `overlay` | dismisses the blocking dialog/banner, verifies, reruns |
| `form-state` | diagnoses unfilled required / invalid fields (DOM + optional screenshot) |
| `assertion-drift` | opt-in: verifies UI text drifted and reruns with the corrected expectation |
| `unknown` | root-cause analysis only |

📙 **[Full documentation](https://manykarim.github.io/robotframework-heal/)** — tutorials, how-to guides, the complete generated `HEAL_*` configuration and CLI reference, and the design/benchmarks behind it.

## Install

```bash
pip install robotframework-heal            # Browser/Playwright + Appium
pip install robotframework-heal[selenium]  # + SeleniumLibrary support
```

## Quickstart

```robotframework
*** Settings ***
Library    Browser    timeout=3s
Library    Heal
```

```bash
# .env (auto-loaded from the working dir upwards; overrides the environment)
HEAL_MODEL=openai/gpt-4.1-nano
HEAL_BASE_URL=https://openrouter.ai/api/v1
HEAL_API_KEY=sk-...
```

```bash
heal doctor --role locator   # verify the endpoint
robot -d results suites/     # heal during the run
```

Then open `results/heal/heal_report.html`.

### Library import

`Library    Heal` is the canonical import. These also work:

```robotframework
Library    heal.rf.HealListener   # fully-qualified equivalent
Library    SelfHealing            # deprecated 0.3 shim (emits a warning)
```

## Configuration

All configuration is read from `HEAL_*` environment variables. The nearest
`.env` (searched from the working directory upwards) is loaded automatically and
**overrides** already-set environment variables. The tables below cover the
common settings; the [full reference](https://manykarim.github.io/robotframework-heal/reference/configuration/)
is generated from the schema and lists every option.

### Model (required)

| Variable | Default | Purpose |
|---|---|---|
| `HEAL_MODEL` | – | Model name (e.g. `MiniMax-M2.5`) or a pydantic-ai provider string (e.g. `openai:gpt-4.1-mini`) |
| `HEAL_BASE_URL` | – | OpenAI-compatible endpoint (vLLM, Ollama, LiteLLM, MiniMax, OpenRouter, …) |
| `HEAL_API_KEY` | – | API key for the endpoint |
| `HEAL_OUTPUT_MODE` | `auto` | Structured-output transport: `auto` / `tool` / `native` / `prompted` |

**Per-role overrides** — each agent role can use its own backend; unset values
fall back to the defaults above:

```bash
HEAL_TRIAGE_MODEL=openai/gpt-4.1-nano        # cheap/fast triage
HEAL_LOCATOR_MODEL=openai/gpt-4.1            # stronger locator healing
# also: HEAL_<ROLE>_BASE_URL / _API_KEY / _OUTPUT_MODE   (ROLE = TRIAGE|LOCATOR|VISION|RCA)
```

### Behaviour / options

| Variable | Default | Purpose |
|---|---|---|
| `HEAL_ENABLED` | `true` | Master switch for the healing engine |
| `HEAL_LOCATOR_TIERS` | `selection` | `selection` (candidates + index pick, ~70% fewer tokens) or `generation` (full-DOM prompt) |
| `HEAL_FIX_TIER` | `report` | Highest fix-application tier: `report` / `patch` / `in-place` |
| `HEAL_WARM_START` | `true` | Reuse healed locators from previous runs (`history.sqlite`) — repeat heals cost zero tokens |
| `HEAL_HEAL_ASSERTIONS` | `false` | Opt-in assertion-drift healing |
| `HEAL_FORM_FILL` | `false` | Opt-in form auto-fill (invents test data; diagnose-only by default) |

### Budgets

| Variable | Default | Purpose |
|---|---|---|
| `HEAL_MAX_FAILURE_SECONDS` | `60` | Wall-clock cap per healing transaction |
| `HEAL_MAX_FAILURE_TOKENS` | `50000` | Token cap per transaction |
| `HEAL_MAX_RUN_TOKENS` | `2000000` | Token cap per run; breach degrades to RCA-only |
| `HEAL_REQUEST_LIMIT` | `8` | Max LLM requests per agent run within a transaction |
| `HEAL_AGENT_RETRIES` | `3` | Output-validator retries per agent run |
| `HEAL_READY_TIMEOUT_SECONDS` | `20` | Max wait for page-ready in timing recovery |

### Reporting

| Variable | Default | Purpose |
|---|---|---|
| `HEAL_REPORT_DIR` | `<RF output dir>/heal` | Where artifacts are written |
| `HEAL_HISTORY_DB` | `<report dir>/history.sqlite` | Cross-run healing history (powers warm start) |

## What you get

After a run, the report directory contains:

- `heal_report.html` — self-contained dashboard (healed *and* unhealed failures, evidence, costs, fix proposals)
- `events.jsonl` — append-only, crash-safe run store
- `summary.json` — for CI gates (e.g. fail above a heal-count threshold)
- `healed_files/` + `diffs/` — read-only fixed copies and word-highlighted diffs (your suites are never modified)
- `heal.patch` — git-appliable fixes (at `HEAL_FIX_TIER=patch`)
- `history.sqlite` — cross-run memory

## CLI

```bash
heal triage results/    # summarize failures, RCAs and fix proposals
heal report results/    # render dashboard + diffs
heal apply results/     # apply fixes (--patch / --in-place)
heal doctor --role all  # probe configured model endpoints
heal history db.sqlite  # repeat-healing hotspots
heal mcp results/        # MCP server for coding agents
```

## Documentation

- **[Getting started](https://manykarim.github.io/robotframework-heal/tutorials/getting-started/)** — heal your first suite
- **[Model providers](https://manykarim.github.io/robotframework-heal/how-to/model-providers/)** — OpenAI, Azure, vLLM, Ollama, MiniMax, OpenRouter, LiteLLM
- **[Configuration reference](https://manykarim.github.io/robotframework-heal/reference/configuration/)** — every `HEAL_*` setting (generated)
- **[Fixing test files](https://manykarim.github.io/robotframework-heal/how-to/fixing-files/)** — diffs, patches, blast radius
- **[Migrating from 0.3](https://manykarim.github.io/robotframework-heal/reference/migration/)**

## Development

```bash
uv sync
uv run invoke heal-utests                     # unit tests (no LLM, no browser)
uv run invoke heal-atests                     # acceptance tests (real browser, no LLM)
uv run invoke heal-atests --live-llm          # + live healing (needs HEAL_* config)
uv run --group docs mkdocs serve              # preview the docs site
```

## License

Apache-2.0.
