# Drive healing from a coding agent

heal exposes its run store and fix engine over an **MCP server**, so a coding
agent (Claude Code, etc.) can triage failures, inspect evidence, and apply fixes
with full judgment — the missing half of in-run healing.

## Start the server

```bash
heal mcp results/        # stdio transport over a run's store
```

## What the agent can do

| Tool | Purpose |
|---|---|
| `list_failures` | ids, statuses, failure classes |
| `get_failure_bundle(event_id)` | full evidence: diagnosis, RCA, DOM/screenshot excerpts, attempts, fix proposal |
| `get_fix_proposals` | proposals with blast radius and usage sites |
| `apply_fix(event_id, in_place, force)` | apply a fix — `shared` blast radius is never applied in place; the agent gets the patch + usage list to decide |
| `healing_history(db_path)` | cross-run hotspots |

## The agent skill

The repo ships an agent skill (`skills/heal/SKILL.md`) describing the
triage → inspect → fix workflow: review failures, respect blast radius (apply
`local` fixes, reason about `shared` ones), never force a dirty tree, and read
the RCA to tell "test outdated" from "application changed". Point your coding
agent at it.

## Why delegate

The in-run engine can heal and propose, but it can't make the judgment calls a
human or coding agent can: whether to change a *variable* or one *usage*, whether
a `shared` fix is safe, whether an unhealed failure is a real app regression. MCP
mode closes that loop.
