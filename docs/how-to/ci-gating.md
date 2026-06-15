# Gate CI on healing results

heal keeps your suite green by healing at runtime, but a *healed* failure still
signals drift you'll want to fix. `summary.json` lets CI act on it.

## summary.json

Written to the report directory after every run:

```json
{
  "transactions": 7,
  "healed": 5,
  "unhealed": 1,
  "suppressed": 0,
  "by_failure_class": { "locator-drift": 5, "timing": 2 },
  "affected_files": ["suites/login.robot"],
  "total_tokens": 8421,
  "fix_proposals": { "total": 5, "local": 4, "shared": 1 }
}
```

## Fail the build above a threshold

```bash
robot -d results suites/

python - <<'PY'
import json, sys
s = json.load(open("results/heal/summary.json"))
if s["healed"] > 5:
    sys.exit(f"::error::{s['healed']} locators needed healing — fix the suite")
PY
```

## GitHub annotations

heal can emit GitHub workflow annotations (one per transaction) so healed and
unhealed failures show inline on the PR — see `heal.report.summary.gha_annotations`
and the [reports reference](../reference/reports.md).

## Tips

- Run with a stable `HEAL_HISTORY_DB` so [warm start](warm-start.md) makes repeat
  heals free across CI runs.
- Set `HEAL_FIX_TIER=patch` to attach a `git apply`-able `heal.patch` as a build
  artifact for reviewers — see [Fix test files](fixing-files.md).
