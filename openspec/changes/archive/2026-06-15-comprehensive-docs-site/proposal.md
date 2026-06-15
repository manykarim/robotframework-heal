# Proposal: comprehensive-docs-site

## Why

The product surface has grown enormously (17 capabilities / 57 requirements, ~30 `HEAL_*` settings, 7 CLI commands, 3 drivers, MCP server, agent skill, 5 benchmarked experiments) while `docs/` still contains only `index.md` and `features.md`. New users cannot discover how to configure model backends, which failure classes exist, how the tiered locator pipeline behaves, or how to read the reports — that knowledge lives scattered across the README, source docstrings, and `experiments/*/FINDINGS.md`. A comprehensive, well-structured documentation site is now the main adoption gap.

The static-site-generator question is effectively settled by ecosystem fit: the Robot Framework project itself is standardizing its new Manual on Material for MkDocs, the project already runs Material (with mermaid), and Material's successor *Zensical* reads the same `mkdocs.yml` — so today's investment is also the future migration path. The real work is information architecture, auto-generated reference (so config/CLI docs never drift from code), diagrams, and deployment.

## What Changes

- **Adopt a Diátaxis information architecture** on the existing Material for MkDocs stack: Tutorials (get healing in 5 minutes), How-to guides (provider setups — vLLM/Ollama/OpenAI/MiniMax/OpenRouter, Selenium, CI gating, fixing files, MCP/coding-agent), Reference (config, CLI, failure classes, drivers), Explanation (failure taxonomy, tiered locator pipeline, capability-tiered models, threading model, root-cause analysis) — the last drawing on the real benchmark data in `experiments/*/FINDINGS.md`.
- **Auto-generate the user-facing reference from code** at build time (no internal/package API reference): the `HEAL_*` configuration reference is generated from the `HealSettings` pydantic schema (env var name, default, constraint, description, grouped by concern); the CLI reference is generated from the Typer app (every command, arguments, options, help). A build hook fails if a setting or command is undocumented, preventing drift.
- **Diagrams and images**: mermaid diagrams for the pipeline, tier ladder, fix-resolution decision tree, and threading model; a "what you get" gallery of committed screenshots of the real HTML dashboard, side-by-side diff, and `heal doctor` output; auto social cards.
- **Versioning infrastructure without per-release docs**: set up `mike` so multiple versions *can* be published later (docs may change between releases), but publish a single rolling version now; the site serves that version by default.
- **GitHub Pages deployment** via a GitHub Actions workflow building the site and publishing through `mike` to the `gh-pages` branch on release/tag and on `main`.

## Capabilities

### New Capabilities

- `documentation-site`: the documentation site — Material for MkDocs stack, Diátaxis structure and content coverage, diagrams/screenshots, mike-based versioning (multi-version capable, single version published), GitHub Pages deployment.
- `generated-reference`: build-time generation of the user-facing configuration reference (from `HealSettings`) and CLI reference (from the Typer app), with a completeness guard that fails the build on any undocumented setting or command.

### Modified Capabilities

None — documentation is a new concern; no existing product capability changes behavior.

## Impact

- **Code**: `mkdocs.yml` (plugins, nav, theme features), `docs/**` (new IA pages, images), `docs/gen_reference.py` (gen-files hook introspecting `HealSettings` + Typer), `.github/workflows/docs.yml` (new), possibly small `description=` additions to per-role settings fields so the generated reference is complete.
- **Dependencies (docs group)**: + `mkdocs-gen-files`, `mike`; `mkdocs-material` retained; no runtime dependencies added.
- **Users**: a published site at the existing GitHub Pages URL; the README slims to a pointer plus quickstart.
- **Risk**: generated reference depending on schema introspection → completeness test in CI; versioning misconfiguration → documented `mike` deploy flow and a dry-run in the workflow; Material maintenance mode → mitigated by the Zensical-reads-`mkdocs.yml` migration path (out of scope to adopt now).
