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
