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

📙 **[Full documentation](https://manykarim.github.io/robotframework-heal/)** — tutorials, how-to guides, the complete `HEAL_*` configuration and CLI reference, and the design/benchmarks behind it.

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
# .env (auto-loaded, overrides the environment)
HEAL_MODEL=openai/gpt-4.1-nano
HEAL_BASE_URL=https://openrouter.ai/api/v1
HEAL_API_KEY=sk-...
```

```bash
heal doctor --role locator   # verify the endpoint
robot -d results suites/     # heal during the run
```

Then open `results/heal/heal_report.html`. Any OpenAI-compatible endpoint works
(vLLM, Ollama, LiteLLM, MiniMax, OpenRouter) — capability is probed, not assumed,
and small models work via a prompted-JSON floor.

## Documentation

- **[Getting started](https://manykarim.github.io/robotframework-heal/tutorials/getting-started/)** — heal your first suite
- **[Model providers](https://manykarim.github.io/robotframework-heal/how-to/model-providers/)** — OpenAI, Azure, vLLM, Ollama, MiniMax, OpenRouter, LiteLLM
- **[Configuration reference](https://manykarim.github.io/robotframework-heal/reference/configuration/)** — every `HEAL_*` setting
- **[Fixing test files](https://manykarim.github.io/robotframework-heal/how-to/fixing-files/)** — diffs, patches, blast radius
- **[Migrating from 0.3](https://manykarim.github.io/robotframework-heal/reference/migration/)**

## Development

```bash
uv sync
uv run invoke heal-utests                     # unit tests (no LLM, no browser)
uv run invoke heal-atests                     # acceptance tests (real browser, no LLM)
uv run --group docs mkdocs serve              # preview the docs site
```

## License

Apache-2.0.
