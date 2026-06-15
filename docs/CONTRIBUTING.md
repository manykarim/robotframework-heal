# Working on the docs

The site is built with Material for MkDocs and deployed to GitHub Pages via
`mike` (multi-version). The configuration and CLI reference are **generated from
code** (`docs/gen_reference.py` → `docs/_refgen.py`), so they never drift.

## Local preview

```bash
uv sync --group docs
DISABLE_MKDOCS_2_WARNING=true uv run --group docs mkdocs serve
```

A strict build (what CI runs on PRs) also fails if any setting lacks a
description or a CLI command is undocumented:

```bash
uv run --group docs mkdocs build --strict
```

## Deployment

`.github/workflows/docs.yml` handles it:

- **Pull requests** — strict build only, no deploy.
- **Push to `main`** — `mike deploy --push --update-aliases latest` updates the
  rolling version.
- **Published release** — additionally `mike deploy --push <tag>` publishes a
  pinned version that appears in the version selector alongside `latest`.

### GitHub Pages

Pages is already enabled for this repository, serving from the `gh-pages` branch
(root) at `https://manykarim.github.io/robotframework-heal/`. The `docs` workflow
publishes to that branch via `mike`; no further setup is needed. The first
`mike` deploy converts any pre-existing flat deploy into the versioned layout
(a root redirect to the default `latest/` version).

## Refreshing screenshots

See [`docs/images/README.md`](images/README.md) for the capture recipe.

## Testing and CI

Three tiers, matched to what can run safely in CI:

| Tier | Command | LLM? | Where |
|---|---|---|---|
| Unit | `uv run invoke heal-utests` | no | every PR (`ci.yml`) |
| Acceptance (deterministic) | `uv run invoke heal-atests` | no | every PR (`ci.yml`) — timing recoveries on bundled pages |
| Live end-to-end | `uv run invoke heal-atests --live-llm` | **yes** | `e2e.yml` — push to main, weekly, manual |

The live suites (locator drift, keyword-argument fixing, Selenium, shadow DOM /
iframes) need a real model and run only in `e2e.yml`, not on pull requests
(secrets are unavailable to fork PRs and cost tokens). The external-site demo
suites under `tests/atest/` are exploratory and run neither in CI nor here.

### Configuring live E2E secrets

In **Settings → Secrets and variables → Actions**, set either the new names or
rely on the 0.3 fallback:

- Preferred: secret `HEAL_API_KEY`, variables `HEAL_BASE_URL` and `HEAL_MODEL`.
- Fallback: the workflow reuses secret `LLM_API_KEY` → `HEAL_API_KEY`, secret
  `LLM_API_BASE` → `HEAL_BASE_URL`, and variable `LLM_LOCATOR_MODEL` (stripping a
  leading `openai/`) → `HEAL_MODEL`.

!!! warning
    The 0.3 model id `openai/x-ai/grok-4-fast:free` may be stale (it 404s on
    OpenRouter). Set a current `HEAL_MODEL` variable for reliable E2E runs.

Run them locally with a `.env`:

```bash
HEAL_MODEL=openai/gpt-4.1-nano
HEAL_BASE_URL=https://openrouter.ai/api/v1
HEAL_API_KEY=sk-...
uv run invoke heal-atests --live-llm
```
