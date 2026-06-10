# Overview

A Robot Framework listener for **failure triage, self-healing and root-cause analysis** of UI tests (Browser/Playwright and Appium).

Every failed keyword is classified into a failure class, healed when possible — and always turned into a clean, enriched error record with evidence, healing attempts and a suggested permanent fix.

## Installation

```bash
pip install robotframework-heal
```

## Usage

```robotframework
*** Settings ***
Library    Browser    timeout=5s
Library    heal.rf.HealListener
Suite Setup    New Browser    browser=chromium    headless=True
```

Configure one model for all agent roles (any OpenAI-compatible endpoint — vLLM, Ollama, LiteLLM proxy, MiniMax, OpenRouter — or a pydantic-ai provider string such as `openai:gpt-4.1-mini`):

```bash
HEAL_MODEL=MiniMax-M2.5
HEAL_BASE_URL=https://api.minimax.io/v1
HEAL_API_KEY=your-key
```

Verify the endpoint before a run:

```bash
heal doctor --role all
```

The legacy `Library    SelfHealing` import keeps working as a deprecated shim; see the README migration table.

## Configuration

All settings are `HEAL_*` environment variables (or `.env`):

| Variable | Default | Purpose |
|---|---|---|
| `HEAL_MODEL` / `HEAL_BASE_URL` / `HEAL_API_KEY` | – | default model for all roles |
| `HEAL_TRIAGE_MODEL`, `HEAL_LOCATOR_MODEL`, `HEAL_VISION_MODEL`, `HEAL_RCA_MODEL` | default model | per-role overrides (+ `_BASE_URL`/`_API_KEY`/`_OUTPUT_MODE`) |
| `HEAL_OUTPUT_MODE` | `auto` | structured-output transport: `tool` / `native` / `prompted` |
| `HEAL_MAX_FAILURE_SECONDS` | `60` | wall-clock cap per healing transaction |
| `HEAL_MAX_FAILURE_TOKENS` | `50000` | token cap per transaction |
| `HEAL_MAX_RUN_TOKENS` | `2000000` | run-wide cap; breach degrades to RCA-only |
| `HEAL_READY_TIMEOUT_SECONDS` | `20` | max wait in timing recovery |
| `HEAL_FIX_TIER` | `report` | `report` / `patch` / `in-place` |
| `HEAL_HEAL_ASSERTIONS` | `false` | opt-in assertion-drift healing |
| `HEAL_FORM_FILL` | `false` | opt-in form auto-fill (invents test data) |
| `HEAL_REPORT_DIR` | `<outputdir>/heal` | report/store location |
| `HEAL_HISTORY_DB` | `<report dir>/history.sqlite` | cross-run healing history |
| `HEAL_ENABLED` | `true` | master switch |
