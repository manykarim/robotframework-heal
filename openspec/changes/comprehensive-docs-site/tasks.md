# Tasks: comprehensive-docs-site

## 1. Toolchain and scaffolding

- [x] 1.1 Added docs group (mkdocs-material, mkdocs-gen-files, mike); expanded mkdocs.yml (light/dark palette, nav tabs/sections, code copy/annotate, search, mermaid, mike version provider)
- [x] 1.2 Declared the Diátaxis nav (Home, What you get, Tutorials, How-to, Reference, Explanation); placeholder pages created; `mkdocs build --strict` passes (generated reference pages emitted as placeholders by the gen hook)

## 2. Generated reference (from code)

- [x] 2.1 Added `description=` to all 16 per-role override fields; every `HealSettings` field now has a description (verified)
- [ ] 2.2 Implement `docs/gen_reference.py` (mkdocs-gen-files hook): render the config reference from `HealSettings.model_fields` (env var name, type/enum choices, default, constraints, description, grouped by concern) and the CLI reference from the Typer app (per-command usage/args/options/help)
- [ ] 2.3 Completeness guard: the hook raises if any setting lacks a description or any registered CLI command is not rendered; CI build runs with `--strict`
- [ ] 2.4 Unit test the generator against `HealSettings` and the Typer app (every field + every command rendered; enum choices present)

## 3. Content — Reference

- [ ] 3.1 Failure-classes reference page (the 7 classes: detection signal, healing action, opt-in flags, surfaces) sourced from the deployed specs
- [ ] 3.2 Drivers reference (Browser/Playwright, SeleniumLibrary, Appium): capabilities matrix, shadow-DOM/iframe support, install extras
- [ ] 3.3 Report-artifacts reference (events.jsonl, dashboard, summary.json, diffs/healed_files, history.sqlite) + the 0.3→0.4 `HEAL_*` migration table

## 4. Content — Tutorials and How-to

- [ ] 4.1 Getting-started tutorial: install, add the listener, configure one model, run a suite with a seeded broken locator, read the report
- [ ] 4.2 Provider how-to guides: OpenAI/Azure, MiniMax, OpenRouter, vLLM, Ollama, LiteLLM proxy — each with the exact `HEAL_*` settings and a `heal doctor` check
- [ ] 4.3 Library how-to guides: SeleniumLibrary (`[selenium]` extra, frame limitation), Appium (swipe search)
- [ ] 4.4 Workflow how-to guides: CI gating on `summary.json`; fixing files (report/patch/in-place tiers, blast radius, reviewing diffs); warm start across runs; MCP server + coding-agent skill

## 5. Content — Explanation

- [ ] 5.1 Failure taxonomy + deterministic-then-LLM triage; verification-in-the-loop
- [ ] 5.2 Tiered locator pipeline (candidates → selection → generation) and capability-tiered models, with the benchmark matrices summarized from `experiments/*/FINDINGS.md` (attributed)
- [ ] 5.3 Threading/marshalling model and root-cause analysis (incl. git test-change context); fix blast radius

## 6. Diagrams and images

- [ ] 6.1 Mermaid diagrams: heal pipeline, tiered-locator ladder, fix-origin-resolution decision tree, threading model
- [ ] 6.2 Capture real-output screenshots (dashboard, diff page, `heal doctor`) from an actual run into `docs/images/`; document the capture recipe; add a "What you get" page
- [ ] 6.3 Landing page: value proposition + "what you get" gallery + prominent Get-started CTA

## 7. Versioning and deployment

- [ ] 7.1 Initialize `mike` with a default rolling version (`latest`); verify the version selector renders with one version and `mike serve` works locally
- [ ] 7.2 `.github/workflows/docs.yml`: PRs run `mkdocs build --strict` (no deploy); pushes to the default branch `mike deploy --push --update-aliases` the rolling version to `gh-pages`; document how a release tag adds a pinned version
- [ ] 7.3 Configure the repository for GitHub Pages from `gh-pages`; verify the published site at the existing URL; slim the README to quickstart + site link
