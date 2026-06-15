# Report artifacts

After a run, the report directory (`HEAL_REPORT_DIR`, default
`<RF output dir>/heal/`) contains:

| Artifact | What it is |
|---|---|
| `events.jsonl` | Append-only run store — one typed event per healing transaction, written as it completes (crash-safe). |
| `heal_report.html` | Self-contained dashboard: summary, failure-class breakdown, per-event drill-down with evidence, costs, fix proposals. |
| `summary.json` | Machine-readable counts (healed / unhealed / suppressed, per class, affected files, tokens) for CI gates. |
| `healed_files/` | Read-only fixed copies of affected `.robot`/`.resource` files. **Your originals are never modified.** |
| `diffs/` | Side-by-side HTML diffs (word-level highlighting), one per healed file, plus `index.html`. |
| `heal.patch` | Unified, `git apply`-able patch — only at `HEAL_FIX_TIER=patch` or higher. |
| `history.sqlite` | Cross-run healing history (powers warm start and hotspot detection). |

## The run store (`events.jsonl`)

Each line is a `HealEvent`: the failing keyword, the diagnosis, healing attempts,
the outcome, evidence references, model/output-mode/token usage, the RCA record,
and any fix proposal. It is the unit every report renders from, and it survives a
crashed run. `--rerunfailed` runs merge and deduplicate stores.

## Gating CI

```bash
# fail the build if more than N locators needed healing
python -c "import json,sys; s=json.load(open('results/heal/summary.json')); sys.exit(s['healed'] > 5)"
```

See [Gate CI on results](../how-to/ci-gating.md) for a full workflow, and
[Fix test files](../how-to/fixing-files.md) for the diff/patch/in-place tiers.
