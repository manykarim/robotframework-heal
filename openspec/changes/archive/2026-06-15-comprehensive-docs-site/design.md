# Design: comprehensive-docs-site

## Context

`docs/` currently holds two thin pages on a minimal `mkdocs.yml` (Material theme, mermaid via superfences). The knowledge that needs documenting already exists but is scattered: README (quickstart, config table), source docstrings, the deployed `openspec/specs/` (17 capabilities), and `experiments/*/FINDINGS.md` (real benchmark data — token/accuracy matrices, the threading spike, the model-compatibility findings). Two structural facts shape the build-time generation:

- `HealSettings` (pydantic-settings, `HEAL_` prefix) exposes every setting with a default and, for most, a `description=`; field names map to env vars deterministically (`max_failure_seconds` → `HEAL_MAX_FAILURE_SECONDS`); enums (`OutputMode`, `FixTier`) and constraints (`gt=0`) are introspectable via `model_fields`.
- The CLI is a Typer app with 7 commands, each with typed arguments/options and help strings.

User decisions for this change: no per-release docs but multi-version *capability*; user-facing CLI/config reference only (no internal package API reference); auto-generated reference; GitHub Pages hosting.

## Goals / Non-Goals

**Goals:**
- A navigable, comprehensive site structured by reader intent (Diátaxis).
- Config and CLI reference generated from code so they cannot drift; build fails if something is undocumented.
- Diagrams and real-output screenshots that make behavior legible at a glance.
- Versioning infrastructure that can host multiple versions later, publishing one now.
- Automated GitHub Pages deployment.

**Non-Goals:**
- No internal/package API reference (driver protocol, schemas, engine internals) — user-facing surface only.
- No SSG migration (stay on Material for MkDocs; Zensical revisited when stable).
- No per-release documentation set now (only the infrastructure to add it).
- No rewrite of `experiments/*/FINDINGS.md` — they are sources the explanation pages cite/summarize, not published verbatim.

## Decisions

### D1: Stay on Material for MkDocs

Python-native, in-repo Markdown, already adopted, mermaid wired, and the de-facto standard the Robot Framework Manual itself is moving to — ecosystem fit outweighs any feature delta. Material entered maintenance mode in 2026, but its successor Zensical reads `mkdocs.yml`, so this is the migration path, not a dead end. Alternatives (Sphinx: reST friction/heavier; Docusaurus/Starlight: JS toolchain foreign to RF contributors) rejected on fit.

### D2: Diátaxis information architecture

Four top-level sections by reader intent, mapping existing material onto the right quadrant:

```
Tutorials     → "Heal your first suite" (Browser + a model in 5 min)
How-to        → provider setups (OpenAI/Azure/MiniMax/OpenRouter/vLLM/Ollama/LiteLLM),
                 SeleniumLibrary, Appium, CI gating on summary.json, fixing files
                 (report/patch/in-place), reviewing diffs, MCP + coding agents,
                 warm start across runs, heal doctor
Reference     → config (generated), CLI (generated), failure classes, drivers matrix,
                 report artifacts, env-var migration from 0.3
Explanation   → failure taxonomy, deterministic-then-LLM triage, tiered locator
                 pipeline, capability-tiered models (with the benchmark matrices),
                 verification-in-the-loop, threading model, RCA, fix blast radius
```

Nav is declared in `mkdocs.yml`; generated reference pages slot into Reference.

### D3: Generate reference from code via `mkdocs-gen-files`

A single build-time script (`docs/gen_reference.py`) produces virtual Markdown pages so nothing is hand-duplicated:

- **Config reference**: iterate `HealSettings.model_fields`; for each, render env var name (`HEAL_` + upper(field)), type/enum choices, default, constraints, and description; group by concern (feature switches, default model, per-role overrides, budgets, timing, reporting) using a small ordered grouping map keyed by field name. Per-role override fields (`triage_model`, …) are explained once as a pattern plus a generated table.
- **CLI reference**: drive Typer's own Markdown doc generation (or introspect the `click` object behind the Typer app) to emit one section per command with usage, arguments, options, and help.
- **Completeness guard**: the script asserts every `model_fields` entry and every registered CLI command is rendered; a missing `description=` (or a new undocumented command) raises at build time. CI builds with `--strict`, so drift fails the pipeline.

This requires a few settings fields that currently lack `description=` (the per-role override fields) to gain one — a small source change that improves the single source of truth, in scope because it makes the generated reference complete.

*Alternatives rejected*: hand-written tables (drift at ~30 settings, guaranteed); `mkdocstrings` rendering of the whole package (pulls in internal API surface the user explicitly scoped out).

### D4: Diagrams and screenshots

Mermaid (already enabled) for: the heal pipeline, the tiered-locator ladder, the fix-origin-resolution decision tree, the threading/marshalling model. A committed `docs/images/` gallery of real outputs — HTML dashboard, side-by-side diff page, `heal doctor` console — captured from an actual run (a documented capture recipe so they can be refreshed), shown on a "What you get" page and inline where relevant. Material's `social` plugin generates share cards. Benchmark tables are transcribed from `experiments/*/FINDINGS.md` into explanation pages with attribution to the experiment.

### D5: Versioning with `mike`, one version published

`mike` manages multiple doc versions on the `gh-pages` branch with a version selector. Now: publish a single alias (`latest`) set as default; the selector is present but lists one version. Later, tagging a release can publish a pinned version (`0.4`) alongside `latest`. This satisfies "no per-release docs now, but the option to add versions" and accommodates docs changing between releases.

### D6: GitHub Pages via Actions + `mike`

A `docs.yml` workflow: install the docs dependency group, build, and `mike deploy --push` the rolling version on pushes to `main` (updating `latest`); on a release tag, additionally deploy the pinned version. The site is served from the `gh-pages` branch at the existing `manykarim.github.io/robotframework-heal` URL. PR builds run `mkdocs build --strict` without deploying, so broken links / undocumented settings fail review.

## Risks / Trade-offs

- [Generated reference breaks if introspection assumptions change] → completeness guard + `--strict` build in CI catch it immediately; the gen script is unit-tested against `HealSettings`.
- [`mike` / Pages deploy misconfiguration] → workflow runs a build on PRs (no deploy) and a dry-run; deploy only from `main`/tags with `contents: write` scoped to `gh-pages`.
- [Screenshots go stale as the UI evolves] → a documented capture recipe and a single page that owns them, so refresh is a known chore, not a hunt.
- [Material maintenance mode] → accepted; migration path (Zensical reads `mkdocs.yml`) is real and out of scope here.
- [Scope creep into internal API docs] → explicitly non-goal; gen script only touches `HealSettings` + the Typer app.

## Migration Plan

Additive. README slims to a quickstart + link once the site is live. The existing two `docs/` pages are absorbed/expanded into the new IA. No product behavior changes. Rollback = revert the docs/workflow commits; the site simply stops updating.

## Open Questions

- Default landing page: a marketing-style home (value prop + "what you get" gallery) vs. straight into the tutorial — lean home page with a prominent "Get started" CTA.
- Whether to also publish the benchmark FINDINGS as a dedicated "Benchmarks" explanation page vs. weaving them into the relevant concept pages — likely a dedicated page given how persuasive the data is.
