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

### One-time GitHub Pages setup

After the first `main` deploy creates the `gh-pages` branch, enable Pages once in
the repository settings:

> **Settings → Pages → Build and deployment → Source: _Deploy from a branch_ →
> Branch: `gh-pages` / `(root)`**

The site then serves at `https://manykarim.github.io/robotframework-heal/`.

## Refreshing screenshots

See [`docs/images/README.md`](images/README.md) for the capture recipe.
