# Tasks: comprehensive-docs-site

## 1. Toolchain and scaffolding

- [x] 1.1 Added docs group (mkdocs-material, mkdocs-gen-files, mike); expanded mkdocs.yml (light/dark palette, nav tabs/sections, code copy/annotate, search, mermaid, mike version provider)
- [x] 1.2 Declared the Diátaxis nav (Home, What you get, Tutorials, How-to, Reference, Explanation); placeholder pages created; `mkdocs build --strict` passes (generated reference pages emitted as placeholders by the gen hook)

## 2. Generated reference (from code)

- [x] 2.1 Added `description=` to all 16 per-role override fields; every `HealSettings` field now has a description (verified)
- [x] 2.2 `docs/gen_reference.py`: config reference from `HealSettings.model_fields` (env var, type/enum choices, default, constraints, description, grouped by concern) and CLI reference from the Typer app
- [x] 2.3 Completeness guard inline: raises `SystemExit` if any setting lacks a description or any registered CLI command is unrendered; CI builds with `--strict`
- [x] 2.4 Unit tests: every setting + every CLI command rendered, enum choices/constraints/defaults present, and the completeness guard fires on a missing description (5 tests); refactored pure logic into `docs/_refgen.py`

## 3. Content — Reference

- [x] 3.1 Failure-classes reference (7 classes: detection signal, action, opt-ins, surfaces) + detection-order mermaid
- [x] 3.2 Drivers reference: Browser/Selenium/Appium capability matrix, shadow-DOM/iframe support, install extras, locator syntax
- [x] 3.3 Report-artifacts reference (events.jsonl, dashboard, summary.json, diffs/healed_files, history.sqlite) + 0.3→0.4 migration page

## 4. Content — Tutorials and How-to

- [x] 4.1 Getting-started tutorial: install, listener, configure a model, run with a seeded broken locator, read the report
- [x] 4.2 Provider how-to: tabbed setups for OpenAI/Azure, OpenRouter, MiniMax, vLLM, Ollama, LiteLLM — each with the exact HEAL_* settings and a heal doctor check
- [x] 4.3 Library how-to: SeleniumLibrary ([selenium] extra, frame/shadow/timing limitations) and AppiumLibrary (swipe search, permission popups)
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
