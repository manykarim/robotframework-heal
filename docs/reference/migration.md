# Migrating from 0.3

0.4 is a ground-up rewrite. The `SelfHealing` library still works as a
deprecation shim that routes to the new engine, but configuration moved from
`LLM_*` to `HEAL_*` environment variables.

## Library import

```robotframework
*** Settings ***
# still works (deprecated shim, emits a warning):
Library    SelfHealing

# preferred:
Library    Heal
```

`Library    Heal` is the short, canonical form; `Library    heal.rf.HealListener`
is the equivalent fully-qualified import.

## Configuration

| 0.3 | 0.4 |
|---|---|
| `LLM_API_KEY` / `LLM_API_BASE` | `HEAL_API_KEY` / `HEAL_BASE_URL` |
| `LLM_TEXT_MODEL` / `LLM_LOCATOR_MODEL` | `HEAL_MODEL` / `HEAL_LOCATOR_MODEL` |
| `LLM_VISION_MODEL` | `HEAL_VISION_MODEL` |
| `heal_assertions=True` (kwarg) | `HEAL_HEAL_ASSERTIONS=true` |
| `locator_db_file=...` (kwarg) | `HEAL_HISTORY_DB=...` |
| `fix=`, `use_locator_db`, `collect_locator_info`, `use_llm_for_locator_proposals` | dropped — the run store and capability-resolved proposals replace them |

See the full [configuration reference](configuration.md) for every `HEAL_*`
setting.

## What's new

The 0.4 engine adds failure triage beyond locators (timing, viewport, overlay,
form, assertion), tiered locator selection, cross-run heal memory, a fix engine
with visual diffs, an MCP server and CLI, and capability-tiered model support.
Browse the [Explanation](../explanation/failure-taxonomy.md) section for the
concepts.
